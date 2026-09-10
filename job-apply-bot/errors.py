"""
Traduz exceções técnicas (JSON de erro da API, stack trace) em mensagens
curtas e legíveis, pra mostrar no bot do Telegram ou no terminal sem
despejar um bloco de erro gigante na cara do usuário.
"""


def friendly_error(e: Exception) -> str:
    text = str(e)
    lower = text.lower()

    if "503" in text or "unavailable" in lower or "overloaded" in lower:
        return "O Gemini está sobrecarregado no momento (erro temporário do lado do Google). Tenta de novo em alguns minutos."

    if "429" in text or "resource_exhausted" in lower or "quota" in lower or "rate limit" in lower:
        return "Você atingiu o limite de requisições do Gemini por agora. Espera um pouco ou tenta de novo mais tarde."

    if "timeout" in lower:
        return "A página demorou demais pra carregar. Confere se o link está certo e tenta de novo."

    if "plataforma não suportada" in lower:
        return text  # já é uma mensagem nossa clara, não precisa traduzir

    if "json" in lower and ("decode" in lower or "expecting value" in lower):
        return "O modelo devolveu uma resposta em formato inesperado. Tenta de novo."

    # Fallback: pega só a primeira linha da mensagem de erro, cortada,
    # em vez do texto técnico inteiro (que pode ter centenas de caracteres
    # de JSON aninhado ou traceback).
    first_line = text.strip().split("\n")[0]
    return f"Erro inesperado: {first_line[:200]}"
