import bot
from serp_mvp import notify


def test_unknown_command_shows_help():
    assert bot.handle("hello") == bot.HELP


def test_sheet_commands_need_sheet(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    assert "not connected" in bot.handle("/keywords")


def test_run_without_github_settings(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert "GITHUB_TOKEN" in bot.handle("/run")


def test_summary_lists_new_sites():
    label = {"brands": ["Betway"], "contact": "a@b.com"}
    text = notify.build_summary("2026-11-01", 10, ["interac casino"], [("https://x.com/", label)], "")
    assert "Keywords checked: 9/10" in text
    assert "https://x.com/" in text
    assert "Failed keywords: interac casino" in text
