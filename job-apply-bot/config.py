import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Caminhos do projeto ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESUME_MASTER_PATH = DATA_DIR / "resume_master.json"
OUTPUT_DIR = BASE_DIR / "output"  # PDFs gerados por vaga

OUTPUT_DIR.mkdir(exist_ok=True)

# --- Chave de API do Gemini (vem do .env, nunca hardcoded) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Telegram (vem do .env) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Restringe o bot a responder só você, ignorando qualquer outra pessoa que
# descubra o bot e mande mensagem pra ele.
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Filtros de vaga (usados no modo "search") ---
JOB_FILTERS = {
    "keywords": [
        "desenvolvedor java",
        "desenvolvedor python",
        "desenvolvedor backend",
        "desenvolvedor full stack",
        "engenheiro de software",
    ],
    "exclude_keywords": [
        "sênior",
        "senior",
        "especialista",
    ],
    "locations": [
        "remoto",
        "belo horizonte",
        "minas gerais",
    ],
    "seniority": ["júnior", "junior", "estágio", "trainee"],
}

# --- Modelo do Gemini usado no tailoring ---
GEMINI_MODEL = "gemini-3.6-flash"