import json
from google import genai
from google.genai import types

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import GEMINI_API_KEY, GEMINI_MODEL

client = genai.Client(api_key=GEMINI_API_KEY)


def _build_prompt(resume_data: dict, job_text: str) -> str:
    """
    Monta o prompt mandando os bullets e projetos JÁ COM SEUS IDs.
    Isso é proposital: pedimos pro LLM devolver só os IDs escolhidos (não
    o texto reescrito do zero), então ele fica limitado a selecionar e
    ordenar o que já existe - não tem como "inventar" um bullet novo que
    não estava na lista, porque não existiria um ID pra referenciar.
    """
    bullets_summary = {
        exp["id"]: [{"id": b["id"], "text": b["text"]} for b in exp["bullets"]]
        for exp in resume_data["experience"]
    }
    projects_summary = [
        {"id": p["id"], "name": p["name"], "description": p["description"], "tech": p["tech"]}
        for p in resume_data["projects"]
    ]

    return f"""Você está adaptando um currículo pra uma vaga específica.

DESCRIÇÃO DA VAGA:
{job_text}

BULLETS DE EXPERIÊNCIA DISPONÍVEIS (por experiência, id: texto):
{json.dumps(bullets_summary, ensure_ascii=False, indent=2)}

PROJETOS DISPONÍVEIS:
{json.dumps(projects_summary, ensure_ascii=False, indent=2)}

REGRAS IMPORTANTES:
- NUNCA invente habilidade, tecnologia ou responsabilidade que não esteja nos dados acima.
- Você pode REORDENAR os bullets (mais relevante pra vaga primeiro) e ESCOLHER quais projetos incluir, mas não pode alterar os fatos.
- Escolha no máximo 3 projetos, os mais relevantes pra essa vaga.
- Gere um objetivo profissional curto (2-3 frases) conectando o perfil à vaga, sem inventar experiência.

Responda APENAS com um JSON nesse formato exato, sem texto antes ou depois:
{{
  "objective": "texto do objetivo",
  "bullet_order": {{"id_da_experiencia": ["id_bullet_1", "id_bullet_2", ...]}},
  "selected_project_ids": ["id_projeto_1", "id_projeto_2"]
}}"""


def _call_gemini(prompt: str, temperature: float) -> str:
    """
    Chamada compartilhada entre get_tailoring e answer_questions.
    response_mime_type="application/json" força o Gemini a devolver JSON
    válido - equivalente ao response_format do Groq e ao format="json" do
    Ollama que usamos antes. Mesmo papel, API diferente.
    """
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temperature,
        ),
    )
    return response.text


def get_tailoring(resume_data: dict, job_text: str) -> dict:
    """
    Chama o Gemini e devolve o JSON parseado (objective, bullet_order,
    selected_project_ids). Não aplica nada ainda no currículo - só decide
    o que priorizar. Quem aplica de fato é apply_tailoring(), no
    resume_builder.
    """
    prompt = _build_prompt(resume_data, job_text)
    raw_content = _call_gemini(prompt, temperature=0.3)  # baixo de propósito: seleção consistente, não criatividade

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        print("ERRO: o Gemini não devolveu um JSON válido. Resposta bruta:")
        print(repr(raw_content))
        raise


def answer_questions(resume_data: dict, job_text: str, questions: list[str]) -> dict:
    """
    Recebe uma lista de perguntas do formulário de candidatura (ex: "Por
    que você quer trabalhar aqui?") e devolve um dict {pergunta: resposta}.

    Mesma regra de honestidade do tailoring: as respostas precisam se
    basear só no que está no resume_data - o LLM não deve inventar
    motivação genérica vazia nem fatos que não existem no currículo.
    """
    prompt = f"""Você está respondendo perguntas de um formulário de candidatura a uma vaga.

DESCRIÇÃO DA VAGA:
{job_text}

DADOS REAIS DO CANDIDATO (currículo completo):
{json.dumps(resume_data, ensure_ascii=False, indent=2)}

PERGUNTAS DO FORMULÁRIO:
{json.dumps(questions, ensure_ascii=False, indent=2)}

REGRAS IMPORTANTES:
- Responda cada pergunta em português, tom profissional mas natural (não robótico).
- Baseie as respostas SOMENTE nos dados reais do candidato acima. Nunca invente projetos, empresas ou habilidades que não estão listados.
- Se uma pergunta pedir algo que não há como responder com dados reais (ex: pretensão salarial, disponibilidade), dê uma resposta genérica sensata, sinalizando que é um rascunho a revisar.
- Respostas objetivas: 2-4 frases por pergunta, a não ser que a pergunta claramente peça mais (ex: "descreva um projeto em detalhes").

Responda APENAS com um JSON nesse formato exato, sem texto antes ou depois:
{{"pergunta 1 (texto exato como veio)": "resposta gerada", "pergunta 2 (texto exato)": "resposta gerada"}}"""

    raw_content = _call_gemini(prompt, temperature=0.4)  # um pouco mais alto: queremos texto natural, não só seleção

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        print("ERRO: o Gemini não devolveu um JSON válido. Resposta bruta:")
        print(repr(raw_content))
        raise


if __name__ == "__main__":
    # Teste manual rápido, sem depender do scraper ainda - usa um texto de
    # vaga fictício só pra validar que a chamada ao Gemini funciona.
    from resume_builder.build_pdf import load_resume_data

    resume = load_resume_data()
    fake_job = """
    Vaga: Desenvolvedor Backend Java
    Buscamos profissional com experiência em Java, Spring Boot, APIs REST,
    testes automatizados e bancos relacionais. Diferencial: JWT, Docker.
    """

    print("Chamando o Gemini (deve ser questão de segundos, não minutos)...")
    result = get_tailoring(resume, fake_job)
    print(json.dumps(result, ensure_ascii=False, indent=2))