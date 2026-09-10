import re

# Marcadores que indicam onde o conteúdo ÚTIL da vaga termina e começa o
# "enchimento" (benefícios institucionais, etapas do processo seletivo,
# redes sociais, banner de cookie). Cortamos no primeiro que aparecer -
# tudo que interessa pro tailoring (descrição + requisitos) sempre vem
# ANTES desses marcadores, na ordem real da página.
NOISE_MARKERS = [
    "ETAPAS DO PROCESSO",
    "CONFIRA NOSSAS REDES SOCIAIS",
    "Powered by Gupy",
]


def trim_job_text(raw_text: str, max_chars: int = 4000) -> str:
    """
    Corta o texto bruto da vaga no primeiro marcador de ruído encontrado.
    Se nenhum marcador bater, aplica um limite de caracteres como
    segurança (evita mandar uma página gigante pro LLM à toa).

    Isso reduz bastante o tamanho do prompt, o que por sua vez reduz o
    num_ctx necessário no Ollama - menos RAM disputada, menos chance de
    o sistema cair pra swap (que é o que provavelmente deixou o tailoring
    lento demais).
    """
    for marker in NOISE_MARKERS:
        idx = raw_text.find(marker)
        if idx != -1:
            raw_text = raw_text[:idx]
            break

    return raw_text[:max_chars].strip()


def is_relevant(text: str, filters: dict) -> bool:
    """
    Checa se o texto de uma vaga (título + card inteiro) é relevante,
    com base nas keywords do config.py.

    Regra: pelo menos UMA keyword do config precisa ter TODAS as suas
    palavras presentes no texto (em qualquer posição, não precisa ser a
    frase exata colada) E nenhuma exclude_keyword pode aparecer.

    Por que por palavra e não frase exata: o Gupy escreve títulos com
    sufixo neutro, tipo "Desenvolvedor(a) Java SR" - a frase exata
    "desenvolvedor java" nunca aparece ali por causa do "(a)" no meio,
    mesmo a vaga sendo exatamente o que você quer. Comparando palavra por
    palavra ("desenvolvedor" E "java", cada uma em qualquer lugar do
    texto) isso passa a bater normalmente.
    """
    text_lower = text.lower()

    def phrase_matches(phrase: str) -> bool:
        words = phrase.lower().split()
        return all(word in text_lower for word in words)

    has_keyword = any(phrase_matches(k) for k in filters["keywords"])
    has_exclusion = any(
        keyword.lower() in text_lower for keyword in filters["exclude_keywords"]
    )

    return has_keyword and not has_exclusion


def filter_relevant_jobs(jobs: list[dict], filters: dict) -> list[dict]:
    """
    Aplica is_relevant em uma lista de vagas (dicts com pelo menos
    "title" e "raw_text"), devolvendo só as relevantes.
    """
    relevant = []
    for job in jobs:
        combined_text = f"{job.get('title', '')} {job.get('raw_text', '')}"
        if is_relevant(combined_text, filters):
            relevant.append(job)

    filtered_out = len(jobs) - len(relevant)
    print(f"Filtro de relevância: {len(relevant)} mantidas, {filtered_out} descartadas")

    return relevant


# --- Parser do texto bruto de cada card ---

# Conjuntos de valores conhecidos que o Gupy usa - baseado no card real que
# você me mandou. Se aparecer um valor novo (ex: uma modalidade de trabalho
# que não previmos), ele cai em "location" por eliminação - não quebra,
# só fica no campo errado, e a gente ajusta esse set depois.
WORKPLACE_TYPES = {"Remoto", "Híbrido", "Presencial"}
CONTRACT_TYPES = {
    "Efetivo", "Estágio", "Temporário", "Jovem Aprendiz",
    "Trainee", "Pessoa Jurídica", "Freelancer",
}

DATE_PATTERN = re.compile(r"Publicada em:\s*(\d{2}/\d{2}/\d{4})")


def parse_card_text(raw_text: str, fallback_title: str | None = None) -> dict:
    """
    Recebe o raw_text de um card (texto bruto, linha por linha) e devolve
    campos separados.

    Baseado no card real:
        Stefanini Group          <- linha 0: empresa (posição fixa, sempre 1ª)
        Desenvolvedor(a) Java SR <- linha 1: título (também vem do h3, mas confirma)
        Não informado            <- linha(s) do meio: ordem VARIA
        Remoto                      (às vezes tem "Também p/ PcD", às vezes não)
        Efetivo
        Também p/ PcD
        Publicada em: 09/09/2026 <- última linha: data (posição fixa, sempre por último)

    Por isso empresa e data são pegos por posição (0 e última), mas o meio
    é reconhecido por CONTEÚDO - comparando cada linha contra os conjuntos
    acima - em vez de assumir uma ordem fixa que pode não se repetir.
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    parsed = {
        "company": None,
        "title": fallback_title,
        "location": None,
        "workplace_type": None,
        "contract_type": None,
        "pcd": False,
        "published_date": None,
    }

    if not lines:
        return parsed

    parsed["company"] = lines[0]
    if len(lines) > 1 and not fallback_title:
        parsed["title"] = lines[1]

    # A partir da linha 2 em diante (pulando empresa e título) é onde a
    # ordem varia - percorremos cada linha e testamos o que ela é.
    for line in lines[2:]:
        date_match = DATE_PATTERN.search(line)
        if date_match:
            parsed["published_date"] = date_match.group(1)
            continue

        if "PcD" in line:
            parsed["pcd"] = True
            continue

        if line in WORKPLACE_TYPES:
            parsed["workplace_type"] = line
            continue

        if line in CONTRACT_TYPES:
            parsed["contract_type"] = line
            continue

        # Não bateu com nenhum padrão conhecido -> por eliminação, é local
        # (cidade/estado, ou o texto "Não informado" que vimos no exemplo)
        if parsed["location"] is None:
            parsed["location"] = line

    return parsed