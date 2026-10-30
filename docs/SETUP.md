# Подключение сервисов

Все шаги необязательные и независимые. Ключи вписываются в `.env` (локально), в GitHub Secrets (ежедневный
запуск) и в Render (бот).

## 1. Выдача Google и Gemini

- **SearchApi:** зарегистрироваться на searchapi.io → Dashboard → API Key → `SEARCHAPI_KEY`
  (или SerpApi: serpapi.com → Dashboard → «Your Private API Key» → `SERPAPI_KEY`; достаточно одного).
- **Gemini:** aistudio.google.com/apikey → «Create API key» → `GEMINI_API_KEY`.

## 2. Google Sheets

Программа пишет в таблицу от имени «сервисного аккаунта» - робота Google со своим email.

1. console.cloud.google.com → создать проект (карта не нужна).
2. «APIs & Services» → «Enable APIs» → включить **Google Sheets API**.
3. «IAM & Admin» → «Service Accounts» → «Create service account» (имя любое).
4. Открыть созданный аккаунт → «Keys» → «Add key» → «JSON». Скачается файл, положить его в папку проекта
   как `google-credentials.json` (в git не попадёт).
5. Создать пустую Google-таблицу → «Share» → вставить email сервисного аккаунта (вида `...@...iam.gserviceaccount.com`)
   с правом «Editor».
6. В `.env`: `GOOGLE_SHEET_ID` = часть адреса таблицы между `/d/` и `/edit`,
   `GOOGLE_CREDENTIALS_FILE=google-credentials.json`.

При первом запуске вкладка Keywords заполнится из `keywords.csv`, дальше фразы правятся в таблице.

## 3. Telegram-уведомления

1. В Telegram написать @BotFather → `/newbot` → получить токен → `TELEGRAM_BOT_TOKEN`.
2. Написать своему боту любое сообщение, открыть `https://api.telegram.org/bot<токен>/getUpdates`,
   найти `"chat":{"id":...}` → `TELEGRAM_CHAT_ID`. Несколько чатов - через запятую.
   Бот отвечает только этим чатам.

**Slack (по желанию):** api.slack.com/apps → Create App → Incoming Webhooks → включить → «Add New Webhook»
→ выбрать канал → ссылку в `SLACK_WEBHOOK_URL`.

## 4. Ежедневный запуск (GitHub Actions)

1. Залить проект в репозиторий на GitHub.
2. Settings → Secrets and variables → Actions → «New repository secret» для каждого ключа:
   `SEARCHAPI_KEY`, `GEMINI_API_KEY`, `GOOGLE_SHEET_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `SLACK_WEBHOOK_URL` и `GOOGLE_CREDENTIALS_JSON` (всё содержимое файла `google-credentials.json`).
3. Проверить: Actions → daily → Run workflow. После прогона в репозитории появится коммит «Daily run ...».

## 5. Бот с командами (Render)

1. Токен для запуска прогона: GitHub → Settings → Developer settings → Fine-grained tokens → доступ только к
   этому репозиторию, Permissions: **Actions: Read and write**.
2. render.com → New → Blueprint → выбрать репозиторий (Render прочитает `render.yaml`).
3. Вписать значения: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GITHUB_REPO` (`логин/репозиторий`),
   `GITHUB_TOKEN`, `GOOGLE_SHEET_ID`.
4. В сервисе → Environment → Secret Files → добавить файл `google-credentials.json` с содержимым ключа.
5. После деплоя бот сам регистрирует адрес в Telegram. Написать ему `/status`.

**Локально без Render:** `python bot.py` (бот работает, пока открыто окно).
