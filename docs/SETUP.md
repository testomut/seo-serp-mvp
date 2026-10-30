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

Вписать в `.env` два ключа (бесплатно, без карты) и снова запустить `python main.py`:

- **SearchApi:** searchapi.io → Dashboard → API Key → `SEARCHAPI_KEY`
  (или SerpApi: serpapi.com → Dashboard → «Your Private API Key» → `SERPAPI_KEY`; достаточно одного).
- **Gemini:** aistudio.google.com/apikey → «Create API key» → `GEMINI_API_KEY`.

Этого достаточно: выдача Google по ключам из `keywords.csv`, разметка ИИ, история в `data/serp.db`.

## Бонус: по желанию, каждый пункт независим

### Google Sheets - результат в таблице вместо Excel

1. console.cloud.google.com → новый проект → «Enable APIs» → **Google Sheets API**.
2. «IAM & Admin» → «Service Accounts» → создать → «Keys» → «Add key» → «JSON».
   Файл положить в папку проекта как `google-credentials.json` (в git не попадёт).
3. Создать пустую Google-таблицу → «Share» → email сервисного аккаунта (`...@...iam.gserviceaccount.com`), «Editor».
4. В `.env`: `GOOGLE_SHEET_ID` (часть адреса между `/d/` и `/edit`), `GOOGLE_CREDENTIALS_FILE=google-credentials.json`.

Вкладка Keywords заполнится из `keywords.csv`, дальше фразы правятся в таблице.

### GitHub Actions - прогон сам каждый день

1. Форкнуть репозиторий (или залить свой).
2. Settings → Secrets and variables → Actions → добавить те же ключи, что в `.env`.
   Для Sheets вместо файла - секрет `GOOGLE_CREDENTIALS_JSON` с содержимым `google-credentials.json`.
3. Actions → daily → Run workflow для проверки. Дальше запуск в 07:00 UTC (время - в `daily.yml`).

### Telegram и Slack - сводка после прогона и бот

- **Сводка:** @BotFather → `/newbot` → `TELEGRAM_BOT_TOKEN`. Написать боту, открыть
  `https://api.telegram.org/bot<токен>/getUpdates` → `"chat":{"id":...}` → `TELEGRAM_CHAT_ID`.
- **Бот с командами** (`/run`, `/status`, `/new`, ...): локально `python bot.py`, или бесплатно на Render:
  render.com → New → Blueprint → репозиторий, вписать переменные из `render.yaml`, добавить Secret File
  `google-credentials.json`. Для `/run` нужен `GITHUB_TOKEN`: GitHub → Developer settings → Fine-grained token,
  только этот репозиторий, **Actions: Read and write**.
- **Slack** (только сводка): api.slack.com/apps → Incoming Webhooks → ссылку в `SLACK_WEBHOOK_URL`.
