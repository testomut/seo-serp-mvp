# Запуск у себя

## 1. Без ключей

```bash
git clone https://github.com/testomut/seo-serp-mvp.git && cd seo-serp-mvp
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Работает сразу: демо-выдача, разметка правилами, результат в `results.xlsx`.

## 2. Реальные данные

Вписать в `.env` ключи и снова запустить `python main.py`:

| Что | Сервис | Переменная |
|---|---|---|
| Выдача Google | [SearchApi.io](https://www.searchapi.io) или [SerpApi](https://serpapi.com) (достаточно одного) | `SEARCHAPI_KEY` / `SERPAPI_KEY` |
| Разметка ИИ | [Google AI Studio](https://aistudio.google.com/apikey) (Gemini), [Anthropic](https://console.anthropic.com) (Claude) или [OpenAI](https://platform.openai.com/api-keys) - любой один или несколько | `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |

## Бонус (по желанию)

- **Google Sheets** - результат в таблице вместо Excel, фразы правятся прямо в ней
  (`GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_FILE`, сервисный аккаунт Google).
- **GitHub Actions** - ежедневный запуск по расписанию (`.github/workflows/daily.yml`, ключи в GitHub Secrets).
- **Telegram / Slack** - сводка после прогона и Telegram-бот с командами `/run`, `/status`, `/new`, `/add`
  (`bot.py`, деплой на Render через `render.yaml`).
