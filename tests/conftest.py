"""Applies to every test in tests/: no real keys and no pauses.

bot.py calls load_dotenv() on import, so keys from a local .env would otherwise reach the tests and they
would call real APIs. Tests that need a "connected" service set a fake key themselves (monkeypatch.setenv).
"""
import pytest

from serp_mvp import classify, retry, serp

OTHER_KEYS = (
    "GOOGLE_SHEET_ID", "GOOGLE_CREDENTIALS_FILE",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SLACK_WEBHOOK_URL",
    "GITHUB_REPO", "GITHUB_TOKEN",
)


@pytest.fixture(autouse=True)
def no_keys_no_pauses(monkeypatch):
    llm_keys = [key for _, key, _ in classify.LLMS]
    search_keys = [key for key, _, _ in serp.SERVICES.values()]
    for key in llm_keys + search_keys + list(OTHER_KEYS):
        monkeypatch.delenv(key, raising=False)
    # Retries keep their real logic (attempts, errors), only the waiting is removed
    monkeypatch.setattr(retry.time, "sleep", lambda seconds: None)
