"""
Bot do Telegram: manda o link de uma vaga, recebe o currículo tailored de
volta. Opcionalmente, manda as perguntas do formulário (uma por mensagem)
e recebe as respostas geradas.

Rodar com: python notifier/telegram_bot.py
Precisa ficar rodando (nesse terminal, ou em segundo plano) pra responder
- não é um serviço hospedado, é esse processo mesmo que fica "escutando".
"""
import asyncio
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from pipeline import generate_resume
from tailoring.llm_client import answer_questions
from resume_builder.build_pdf import load_resume_data
from errors import friendly_error

# Estado por conversa - bot pessoal (só você usa), então um dict simples
# em memória basta. Se o bot reiniciar, o estado se perde (aceitável: só
# significa que uma sessão de perguntas em andamento precisaria recomeçar).
sessions = {}


def _is_authorized(update: Update) -> bool:
    """Só responde ao seu chat_id - ignora qualquer outra pessoa."""
    return str(update.effective_chat.id) == str(TELEGRAM_CHAT_ID)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return  # ignora silenciosamente mensagens de quem não é você

    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    session = sessions.setdefault(chat_id, {"collecting_questions": False, "questions": []})

    # --- Se está no meio de coletar perguntas ---
    if session["collecting_questions"]:
        if text.lower() in ("/fim", "fim"):
            questions = session["questions"]
            if not questions:
                await update.message.reply_text("Nenhuma pergunta recebida. Cancelado.")
                session["collecting_questions"] = False
                return

            await update.message.reply_text("Gerando respostas...")
            try:
                answers = await asyncio.to_thread(
                    answer_questions, session["resume"], session["job_text"], questions
                )
            except Exception as e:
                await update.message.reply_text(f"⚠️ {friendly_error(e)}")
                session["collecting_questions"] = False
                session["questions"] = []
                return

            reply_lines = []
            for q, a in answers.items():
                reply_lines.append(f"*P:* {q}\n*R:* {a}")
            await update.message.reply_text("\n\n".join(reply_lines), parse_mode="Markdown")

            session["collecting_questions"] = False
            session["questions"] = []
            return

        session["questions"].append(text)
        await update.message.reply_text(
            f"Anotado ({len(session['questions'])}). Manda mais ou /fim quando acabar."
        )
        return

    # --- Se não está coletando perguntas: espera um link de vaga ---
    if text.startswith("http"):
        await update.message.reply_text("Buscando a vaga e gerando o currículo...")

        try:
            context_data, pdf_path = await asyncio.to_thread(generate_resume, text)
        except Exception as e:
            await update.message.reply_text(f"⚠️ {friendly_error(e)}")
            return

        with open(pdf_path, "rb") as f:
            await update.message.reply_document(document=f, filename="curriculo.pdf")

        # Guarda o contexto dessa vaga na sessão, pra usar se você mandar perguntas depois
        session["job_text"] = context_data["job_text"]
        session["resume"] = load_resume_data()
        session["collecting_questions"] = True

        await update.message.reply_text(
            "Currículo pronto! Se o formulário tiver perguntas abertas, "
            "manda uma por mensagem e digita /fim quando acabar. "
            "Ou digita /fim direto se não tiver nenhuma."
        )
        return

    await update.message.reply_text("Me manda o link de uma vaga do Gupy pra eu processar.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    await update.message.reply_text(
        "Oi! Me manda o link de uma vaga do Gupy que eu gero seu currículo tailored."
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado no .env")
    if not TELEGRAM_CHAT_ID:
        raise ValueError(
            "TELEGRAM_CHAT_ID não configurado no .env - "
            "sem isso o bot não sabe quem é você e vai ignorar todas as mensagens"
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # /fim é tratado dentro de handle_message (não como comando separado)
    # pra simplificar a lógica de estado - registramos ele aqui só pra
    # capturar o caso de vir como comando mesmo (/fim) em vez de texto puro
    app.add_handler(CommandHandler("fim", handle_message))

    print("Bot rodando. Ctrl+C pra parar.")
    app.run_polling()


if __name__ == "__main__":
    main()