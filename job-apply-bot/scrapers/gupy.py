from urllib.parse import urlencode
from playwright.sync_api import sync_playwright, Page

# Precisa vir ANTES de qualquer "from scrapers..." ou "from config...":
# adiciona a raiz do projeto ao sys.path pra esses imports funcionarem
# mesmo rodando "python scrapers/gupy.py" direto (que só põe scrapers/
# no path por padrão, não a raiz).
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scrapers.common import filter_relevant_jobs, parse_card_text, trim_job_text

BASE_URL = "https://portal.gupy.io/job-search/"


def build_search_url(term: str, remote_only: bool = True) -> str:
    """
    Monta a URL de busca do Gupy. O padrão de query string do Gupy é meio
    incomum: em vez de "?term=x", os parâmetros ficam direto no path,
    separados por "&", tipo: /job-search/term=x&workplaceTypes[]=remote

    urlencode() cuida de transformar espaços e acentos em %XX (ex: "java "
    -> "java%20"), senão a URL quebra com termos de busca com espaço.
    """
    params = {"term": term}
    query = urlencode(params)

    if remote_only:
        query += "&workplaceTypes[]=remote"

    return f"{BASE_URL}{query}"


def scrape_search_results(page: Page, term: str) -> list[dict]:
    """
    Abre a busca e extrai os cards de vaga.

    Estratégia: em vez de tentar mapear CADA div do card pra um campo
    específico (empresa, local, tipo de contrato...), pegamos o texto
    inteiro de cada <li> e o link. Cards de vaga em sites assim costumam
    ter uma ordem visual fixa (empresa, título, local, tipo, data), então
    dá pra extrair o texto bruto agora e refinar o parsing linha-a-linha
    depois de ver o resultado real - é mais seguro que adivinhar uma classe
    CSS errada e o scraper quebrar silenciosamente.
    """
    url = build_search_url(term)
    page.goto(url)

    # Espera o container aparecer - ele só existe depois que o JS da SPA
    # roda e busca os dados. Sem esse wait, o Playwright tentaria ler a
    # página vazia (o "HTML quase sem conteúdo" que vimos antes).
    page.wait_for_selector("#job-listing-results", timeout=15000)

    cards = page.locator("#job-listing-results li")
    total = cards.count()
    print(f"Encontrados {total} cards na página (Gupy mostra 12 por busca nessa versão, sem paginação implementada ainda)")

    results = []
    for i in range(total):
        card = cards.nth(i)

        # Um <li> vazio (placeholder de layout) não tem link - pula.
        links = card.locator("a")
        if links.count() == 0:
            continue

        href = links.first.get_attribute("href")

        # h3 com essa classe MUI é o título, conforme vimos no DevTools
        title_locator = card.locator("h3.MuiTypography-heading-small")
        title = title_locator.first.inner_text() if title_locator.count() > 0 else None

        raw_text = card.inner_text()

        # "Banco de Talentos" é cadastro genérico de interesse, não uma
        # vaga com cargo definido - não tem descrição pra tailoring nem
        # processo de candidatura normal, então pulamos essas.
        if "Banco de Talentos" in raw_text:
            continue

        # parse_card_text separa empresa/local/tipo de contrato/data a
        # partir do raw_text, usando o formato real que confirmamos rodando
        # o scraper (empresa na 1ª linha, data na última, meio por conteúdo)
        parsed = parse_card_text(raw_text, fallback_title=title)

        results.append({
            **parsed,
            "url": href,
            "raw_text": raw_text,  # mantido como backup, caso o parser erre algo
        })

    # Filtra por relevância (keywords do config.py) antes de devolver -
    # assim o resto do pipeline nunca vê vaga fora do que você quer.
    return filter_relevant_jobs(results, JOB_FILTERS)


def scrape_job_detail(page: Page, job_url: str) -> str:
    """
    Abre a página de uma vaga específica e devolve o texto inteiro visível.
    Não tentamos separar "descrição" de "responsabilidades" em campos
    diferentes aqui - o LLM na etapa de tailoring recebe esse texto corrido
    e consegue extrair o que precisa dele.
    """
    page.goto(job_url)

    # Texto que sempre aparece quando o conteúdo real carregou (visto no
    # print da página de detalhe) - esperamos por ele em vez de um tempo
    # fixo de sleep, que seria mais lento ou mais frágil.
    page.wait_for_selector("text=DESCRIÇÃO DA VAGA", timeout=15000)

    full_text = page.inner_text("body")
    return trim_job_text(full_text)


def scrape_multiple_terms(page: Page, terms: list[str]) -> list[dict]:
    """
    Roda scrape_search_results() pra cada termo da lista e junta tudo,
    removendo vagas repetidas (a mesma vaga pode aparecer em buscas
    diferentes, ex: "backend" e "full stack" retornam a mesma vaga).

    Deduplicamos pela URL porque é o único campo garantidamente único por
    vaga - título pode se repetir entre empresas diferentes.
    """
    seen_urls = set()
    all_jobs = []

    for term in terms:
        print(f"\nBuscando: '{term}'...")
        jobs = scrape_search_results(page, term)

        new_count = 0
        for job in jobs:
            if job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                job["matched_term"] = term  # útil pra debug: qual busca achou essa vaga
                all_jobs.append(job)
                new_count += 1

        print(f"  {len(jobs)} vagas encontradas, {new_count} novas (sem duplicar)")

    return all_jobs


if __name__ == "__main__":
    # Teste manual: roda isso direto (python scrapers/gupy.py) pra ver
    # o formato real do raw_text antes de escrevermos o parser refinado.
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from config import JOB_FILTERS

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False = você VÊ o navegador agindo, bom pra debugar
        page = browser.new_page()

        jobs = scrape_multiple_terms(page, JOB_FILTERS["keywords"])

        print(f"\n--- Total: {len(jobs)} vagas únicas encontradas ---")
        if jobs:
            first = jobs[0]
            print("\nPrimeira vaga já parseada:")
            print(f"  Empresa: {first['company']}")
            print(f"  Título: {first['title']}")
            print(f"  Local: {first['location']}")
            print(f"  Modelo: {first['workplace_type']}")
            print(f"  Contrato: {first['contract_type']}")
            print(f"  PcD: {first['pcd']}")
            print(f"  Publicada em: {first['published_date']}")
            print(f"  Link: {first['url']}")
            print(f"  Achada pelo termo: {first['matched_term']}")

        browser.close()