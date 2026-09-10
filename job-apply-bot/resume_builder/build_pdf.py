import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import RESUME_MASTER_PATH, OUTPUT_DIR


def load_resume_data() -> dict:
    """Lê o resume_master.json e devolve como dict Python."""
    with open(RESUME_MASTER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def render_resume_pdf(
    resume_data: dict,
    objective_override: str | None = None,
    output_filename: str = "curriculo.pdf",
) -> Path:
    """
    Renderiza o resume_master.json no template HTML e gera um PDF.

    objective_override existe porque, no pipeline final, o LLM vai gerar um
    objetivo específico pra cada vaga (lembra do "objective_variants" no JSON?).
    Por enquanto, sem tailoring ainda, usamos o objetivo default do próprio JSON.
    """
    # Environment é o "motor" do Jinja2: ele sabe onde procurar os templates.
    # FileSystemLoader aponta pra pasta onde está o template.html
    env = Environment(loader=FileSystemLoader(Path(__file__).parent))
    template = env.get_template("template.html")

    objective = objective_override or resume_data["objective_variants"]["default"]

    # render() troca cada {{ variavel }} do template pelo valor correspondente.
    # As chaves do dicionário abaixo viram exatamente os nomes usados no HTML
    # (personal, experience, projects, etc. — batem 1:1 com o template.html)
    html_content = template.render(
        personal=resume_data["personal"],
        objective=objective,
        experience=resume_data["experience"],
        projects=resume_data["projects"],
        education=resume_data["education"],
        skills=resume_data["skills"],
        languages_spoken=resume_data["languages_spoken"],
    )

    output_path = OUTPUT_DIR / output_filename

    # HTML(string=...) recebe o HTML já preenchido (texto puro) e write_pdf
    # faz o trabalho pesado de layout + rasterização pro formato PDF.
    HTML(string=html_content).write_pdf(str(output_path))

    return output_path


def apply_tailoring(resume_data: dict, tailoring: dict) -> dict:
    """
    Recebe o resume_master.json original + o JSON que o LLM devolveu
    (objective, bullet_order, selected_project_ids) e monta uma NOVA
    versão do resume_data já reordenada/filtrada, pronta pra passar
    direto pro render_resume_pdf.

    Trabalha em cima de uma cópia - nunca modifica o resume_data original,
    que é a fonte de verdade e deve continuar intacta pra próxima vaga.
    """
    import copy
    tailored = copy.deepcopy(resume_data)

    # Reordena os bullets de cada experiência conforme bullet_order.
    # Se o LLM não especificou uma experiência (ou pulou algum bullet),
    # mantemos a ordem original como fallback - nunca perdemos informação.
    bullet_order = tailoring.get("bullet_order", {})
    for exp in tailored["experience"]:
        order = bullet_order.get(exp["id"])
        if not order:
            continue
        bullets_by_id = {b["id"]: b for b in exp["bullets"]}
        # Reordena pelos ids que o LLM mandou; ids desconhecidos são ignorados
        reordered = [bullets_by_id[bid] for bid in order if bid in bullets_by_id]
        # Qualquer bullet que o LLM esqueceu de mencionar ainda entra no fim,
        # pra garantir que nenhuma informação real suma do currículo
        remaining = [b for b in exp["bullets"] if b["id"] not in order]
        exp["bullets"] = reordered + remaining

    # Filtra e ordena os projetos pelos ids selecionados
    selected_ids = tailoring.get("selected_project_ids", [])
    if selected_ids:
        projects_by_id = {p["id"]: p for p in tailored["projects"]}
        tailored["projects"] = [
            projects_by_id[pid] for pid in selected_ids if pid in projects_by_id
        ]

    return tailored


if __name__ == "__main__":
    # Teste rápido: gera um PDF "base", sem tailoring, só pra validar o pipeline.
    data = load_resume_data()
    path = render_resume_pdf(data)
    print(f"PDF gerado em: {path}")