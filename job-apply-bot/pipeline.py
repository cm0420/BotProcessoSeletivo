"""
Lógica principal do pipeline (vaga -> currículo tailored), compartilhada
entre o main.py (uso via terminal) e o notifier/telegram_bot.py (uso via
Telegram). Ter isso num lugar só evita duplicar a mesma lógica duas vezes.
"""
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

from scrapers.gupy import scrape_job_detail
from tailoring.llm_client import get_tailoring
from resume_builder.build_pdf import load_resume_data, apply_tailoring, render_resume_pdf


def detect_platform(url: str) -> str:
    domain = urlparse(url).netloc
    if "gupy.io" in domain:
        return "gupy"
    raise ValueError(f"Plataforma não suportada ainda: {domain}")


def generate_resume(job_url: str) -> tuple[dict, str]:
    """
    Pega a descrição da vaga, gera o tailoring e o PDF do currículo.
    Devolve (dict com job_text/tailoring/platform, caminho do PDF).
    """
    platform = detect_platform(job_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if platform == "gupy":
            job_text = scrape_job_detail(page, job_url)
        else:
            browser.close()
            raise NotImplementedError(f"Scraper de detalhe ainda não existe pra {platform}")

        browser.close()

    resume = load_resume_data()
    tailoring = get_tailoring(resume, job_text)

    tailored_resume = apply_tailoring(resume, tailoring)
    pdf_path = render_resume_pdf(
        tailored_resume,
        objective_override=tailoring["objective"],
        output_filename=f"curriculo_{platform}.pdf",
    )

    return {"tailoring": tailoring, "job_text": job_text, "platform": platform}, str(pdf_path)
