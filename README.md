# BotProcessoSeletivo

Bot pessoal para automatizar parte do processo de candidatura a vagas: a partir do link de uma vaga (atualmente Gupy), ele extrai a descrição, usa o Gemini para selecionar e ordenar os bullets do currículo mestre que mais fazem sentido para aquela vaga, e gera um PDF do currículo já tailored. Opcionalmente também rascunha respostas para perguntas do formulário de candidatura, e pode ser operado via Telegram.

## Como funciona

1. **Scraping** (`job-apply-bot/scrapers/`) — abre a vaga com Playwright e extrai o texto relevante (descrição + requisitos), cortando ruído institucional (benefícios, redes sociais, etc.).
2. **Tailoring** (`job-apply-bot/tailoring/`) — manda o texto da vaga e os bullets/projetos do `data/resume_master.json` (cada um com um ID) para o Gemini, que devolve apenas os IDs escolhidos e a ordem — nunca texto reescrito, então não há risco de o modelo inventar experiência.
3. **Geração do currículo** (`job-apply-bot/resume_builder/`) — renderiza um template HTML (Jinja2) com os bullets selecionados e converte para PDF com WeasyPrint.
4. **Notificação** (`job-apply-bot/notifier/`) — bot do Telegram que recebe o link da vaga e devolve o PDF, ou repassa perguntas do formulário para gerar respostas.

## Requisitos

- Python 3.11+
- Uma API key do Gemini ([aistudio.google.com/apikey](https://aistudio.google.com/apikey), free tier)
- Um bot do Telegram (opcional, só para o modo notifier), criado via [@BotFather](https://t.me/BotFather)

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

Copie `.env.example` para `.env` e preencha:

```
GEMINI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Preencha seus dados em `data/resume_master.json` (experiências, projetos, skills — cada bullet com um `id` único, usado pelo tailoring).

## Uso

`main.py` fica na raiz do projeto mas importa módulos de dentro de `job-apply-bot/`, então é preciso rodar com `job-apply-bot` no `PYTHONPATH` (a partir da raiz do repositório):

Gerar apenas o currículo tailored para uma vaga:

```bash
PYTHONPATH=job-apply-bot python main.py link "https://portal.gupy.io/job-search/..."
```

Gerar o currículo e rascunhar respostas para perguntas do formulário (perguntas digitadas manualmente no terminal):

```bash
PYTHONPATH=job-apply-bot python main.py link "https://portal.gupy.io/job-search/..." --answers
```

Buscar vagas pelos termos configurados em `job-apply-bot/config.py` (`JOB_FILTERS`):

```bash
PYTHONPATH=job-apply-bot python main.py search
```

Rodar o bot do Telegram (fica escutando enquanto o processo estiver ativo):

```bash
PYTHONPATH=job-apply-bot python job-apply-bot/notifier/telegram_bot.py
```

## Estrutura

```
job-apply-bot/
├── config.py           # paths, chaves de API, filtros de vaga
├── errors.py            # traduz erros técnicos em mensagens legíveis
├── pipeline.py           # orquestra scraping -> tailoring -> PDF
├── main.py
├── scrapers/             # extração de dados da vaga (por plataforma)
├── tailoring/            # integração com o Gemini
├── resume_builder/       # template + geração de PDF
└── notifier/             # bot do Telegram
data/
└── resume_master.json    # currículo mestre (fonte única de verdade)
```

## Aviso

Projeto pessoal, feito para uso individual. Respeite os termos de uso das plataformas de vagas ao automatizar scraping/candidaturas.
