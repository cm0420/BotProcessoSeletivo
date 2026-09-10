import argparse
from playwright.sync_api import sync_playwright

from pipeline import generate_resume
from scrapers.gupy import scrape_multiple_terms
from tailoring.llm_client import answer_questions
from resume_builder.build_pdf import load_resume_data
from config import JOB_FILTERS


def mode_resume_only(job_url: str):
    """MODO PADRÃO: só currículo."""
    context_data, pdf_path = generate_resume(job_url)
    print(f"Currículo gerado: {pdf_path}")


def mode_with_answers(job_url: str):
    """
    MODO --answers: currículo + respostas do formulário de candidatura.
    Você digita as perguntas que vê no seu navegador (logado manualmente),
    o bot responde com base no job_text/resume já carregados.
    """
    context_data, pdf_path = generate_resume(job_url)
    print(f"Currículo gerado: {pdf_path}")

    resume = load_resume_data()
    job_text = context_data["job_text"]

    print("\n--- Modo perguntas ---")
    print("Digita cada pergunta do formulário abaixo (uma por linha).")
    print("Quando terminar, digita só 'fim' numa linha vazia.\n")

    questions = []
    while True:
        question = input(f"Pergunta {len(questions) + 1} (ou 'fim'): ").strip()
        if question.lower() == "fim":
            break
        if question:
            questions.append(question)

    if not questions:
        print("Nenhuma pergunta digitada, encerrando.")
        return

    print("\nGerando respostas com base no currículo e na vaga...")
    answers = answer_questions(resume, job_text, questions)

    print("\n--- Respostas geradas ---\n")
    for question, answer in answers.items():
        print(f"P: {question}")
        print(f"R: {answer}\n")

    answers_path = pdf_path.replace(".pdf", "_respostas.txt")
    with open(answers_path, "w", encoding="utf-8") as f:
        for question, answer in answers.items():
            f.write(f"P: {question}\nR: {answer}\n\n")

    print(f"Respostas salvas em: {answers_path}")


def search_and_notify() -> list[dict]:
    """MODO search: busca vagas nos termos do config.py."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        jobs = scrape_multiple_terms(page, JOB_FILTERS["keywords"])
        browser.close()
    return jobs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot de candidaturas automatizadas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    link_parser = subparsers.add_parser("link", help="Processa uma vaga a partir do link")
    link_parser.add_argument("url", help="URL da vaga")
    link_parser.add_argument(
        "--answers", action="store_true",
        help="Também gera rascunho das respostas do formulário"
    )

    subparsers.add_parser("search", help="Busca vagas pelos termos do config.py")

    args = parser.parse_args()

    if args.command == "link":
        if args.answers:
            mode_with_answers(args.url)
        else:
            mode_resume_only(args.url)

    elif args.command == "search":
        jobs = search_and_notify()
        print(f"\n{len(jobs)} vagas encontradas no total.")