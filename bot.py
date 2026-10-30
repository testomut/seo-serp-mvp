"""Telegram bot: a remote control for the pipeline. It stores nothing itself.

/run starts the GitHub Actions workflow, the other commands read or edit the Google Sheet.

Two ways to run it:
- on Render (webhook):  gunicorn bot:app      Telegram sends each message to this web app
- locally (polling):    python bot.py         the bot asks Telegram for new messages in a loop
"""
import hashlib
import logging
import os
import time

import requests
from dotenv import load_dotenv
from flask import Flask, request

from serp_mvp import notify, sheets

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}"
ALLOWED_CHATS = (os.getenv("TELEGRAM_CHAT_ID") or "").split(",")

HELP = """Commands:
/run - start a new run now (results in a few minutes)
/status - date of the last run and totals
/new - relevant sites (best positions first)
/keywords - keywords being tracked
/add <keyword> - track a new keyword
/remove <keyword> - stop tracking a keyword"""


# ---------- commands ----------

def handle(text):
    """Turn one message into one reply."""
    command, _, argument = text.strip().partition(" ")
    command = command.split("@")[0].lower()  # "/run@MyBot" in group chats -> "/run"
    argument = argument.strip()

    if command == "/run":
        return start_github_run()
    if command not in ("/status", "/new", "/keywords", "/add", "/remove"):
        return HELP
    if not sheets.enabled():
        return "Google Sheet is not connected, this command needs it."

    if command == "/status":
        return status()
    if command == "/new":
        return relevant_sites()
    if command == "/keywords":
        return "Tracked keywords:\n" + "\n".join(sheets.read_keywords())
    if command == "/add":
        if not argument:
            return "Usage: /add online casino alberta"
        sheets.add_keyword(argument)
        return f"Added: {argument}. It will be searched on the next run."
    if command == "/remove":
        if not argument:
            return "Usage: /remove interac casino"
        if sheets.deactivate_keyword(argument):
            return f"Stopped tracking: {argument}. Its history is kept."
        return f"Keyword not found: {argument}"


def start_github_run():
    repo, token = os.getenv("GITHUB_REPO"), os.getenv("GITHUB_TOKEN")
    if not (repo and token):
        return "GITHUB_REPO / GITHUB_TOKEN are not set, can't start a run."
    response = requests.post(
        f"https://api.github.com/repos/{repo}/actions/workflows/daily.yml/dispatches",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"ref": "main"},
        timeout=20,
    )
    if response.status_code == 204:
        return "Run started. I'll send the summary when it's done (usually 5-15 minutes)."
    return f"GitHub refused to start the run ({response.status_code}): {response.text[:200]}"


def read_tab(title):
    return sheets.open_spreadsheet().worksheet(title).get_all_values()


def status():
    positions = read_tab("Positions")
    sites = read_tab("Sites")[1:]
    last_run = positions[0][-1] if positions and len(positions[0]) > 3 else "never"
    relevant = sum(1 for row in sites if row[2] == "yes")
    return (f"Last run: {last_run}\nSites checked: {len(sites)}\nRelevant: {relevant}\n"
            f"Table: {sheets.sheet_url()}")


def relevant_sites():
    rows = [row for row in read_tab("Sites")[1:] if row[2] == "yes"]
    if not rows:
        return "No relevant sites yet."
    lines = []
    for row in rows[:10]:  # the tab is already sorted by best position
        lines.append(f"#{row[8]} {row[0]}\n  brands: {row[4] or '-'}\n  contact: {row[5] or '-'}")
    return "\n\n".join(lines) + f"\n\nAll {len(rows)}: {sheets.sheet_url()}"


def reply(chat_id, text):
    try:
        answer = handle(text)
    except Exception as error:
        log.exception("Command failed")
        answer = f"Something went wrong: {error}"
    notify.send_telegram(chat_id, answer)


def on_update(update):
    """One Telegram update: reply only to allowed chats, ignore everyone else."""
    message = update.get("message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    if message.get("text") and chat_id in ALLOWED_CHATS:
        reply(chat_id, message["text"])


# ---------- Render: webhook mode ----------

app = Flask(__name__)


@app.get("/")
def health():
    return "ok"


def webhook_secret():
    """Telegram allows only letters, digits, "_" and "-" in the secret, while Render's generated
    value may contain "+/=". A hash of it always fits."""
    return hashlib.sha256(os.getenv("TELEGRAM_WEBHOOK_SECRET", "").encode()).hexdigest()


@app.post("/telegram")
def telegram_webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != webhook_secret():
        return "forbidden", 403
    on_update(request.get_json(force=True))
    return "ok"


if os.getenv("RENDER_EXTERNAL_URL"):  # Render sets this variable to the service's public address
    missing = [name for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET")
               if not os.getenv(name)]
    if missing:
        log.error("Webhook not registered, missing environment variables: %s", ", ".join(missing))
    else:
        answer = requests.post(f"{TELEGRAM_API}/setWebhook", json={
            "url": os.getenv("RENDER_EXTERNAL_URL") + "/telegram",
            "secret_token": webhook_secret(),
        }, timeout=20).json()
        log.info("Telegram webhook: %s", answer)


# ---------- local: polling mode ----------

if __name__ == "__main__":
    requests.post(f"{TELEGRAM_API}/deleteWebhook", timeout=20)  # polling and webhook can't work together
    log.info("Bot is running locally. Press Ctrl+C to stop.")
    offset = 0
    while True:
        try:
            updates = requests.get(f"{TELEGRAM_API}/getUpdates",
                                   params={"offset": offset, "timeout": 30}, timeout=40).json()
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                on_update(update)
        except requests.RequestException as error:
            log.warning("Telegram unavailable (%s), retrying in 5s", error)
            time.sleep(5)
