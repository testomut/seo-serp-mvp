"""Step 5: send the run summary to Telegram and/or Slack (whichever is configured in .env)."""
import logging
import os

import requests

log = logging.getLogger(__name__)


def send(text):
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        send_telegram(os.getenv("TELEGRAM_CHAT_ID"), text)
    if os.getenv("SLACK_WEBHOOK_URL"):
        try:
            requests.post(os.getenv("SLACK_WEBHOOK_URL"), json={"text": text}, timeout=20).raise_for_status()
        except Exception as error:
            log.warning("Slack message failed: %s", error)


def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": text,
                                            "disable_web_page_preview": True}, timeout=20)
        response.raise_for_status()
    except Exception as error:
        log.warning("Telegram message failed: %s", error)


def build_summary(run_date, status, keyword_count, failed_keywords, short_keywords, new_relevant, sheet_link):
    """status: ok / partial / failed. new_relevant: list of (url, label) for sites first found relevant."""
    lines = [f"SEO run {run_date} finished: {status}",
             f"Keywords checked: {keyword_count - len(failed_keywords)}/{keyword_count}",
             f"New relevant sites: {len(new_relevant)}"]
    for url, label in new_relevant[:10]:
        brands = ", ".join(label["brands"][:5]) or "-"
        lines.append(f"\n{url}\n  brands: {brands}\n  contact: {label['contact'] or '-'}")
    if len(new_relevant) > 10:
        lines.append(f"\n...and {len(new_relevant) - 10} more in the table")
    if failed_keywords:
        lines.append("\nFailed keywords: " + ", ".join(failed_keywords))
    if short_keywords:
        lines.append("\nFewer than 10 results from Google: " + ", ".join(short_keywords))
    if sheet_link:
        lines.append(f"\nTable: {sheet_link}")
    return "\n".join(lines)
