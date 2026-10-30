"""LLM calls are replaced with fakes: no keys and no network needed."""
import pytest
import requests

from serp_mvp import classify, retry

PAGE = {"title": "Best casinos", "text": "Jackpot City review", "emails": ["a@b.com"], "contact_links": []}
ANSWER = ('{"site_type": "review", "relevant": true, "brands": ["Jackpot City", "Jackpot City Casino"], '
          '"contact": "a@b.com", "reason": "Ranking of casinos"}')


@pytest.fixture(autouse=True)
def no_keys_no_pauses(monkeypatch):
    for _, key, _ in classify.LLMS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(retry.time, "sleep", lambda seconds: None)


def test_without_keys_rules_decide():
    label = classify.classify("https://site.example/", PAGE, ["Jackpot City"])
    assert label["method"] == "rules"


def test_claude_answer_wrapped_in_markdown():
    label = classify.to_label("```json\n" + ANSWER + "\n```", "claude (test)")
    assert label["relevant"] is True
    assert label["brands"] == ["Jackpot City"]  # spelling variants merged


def test_next_llm_is_used_when_first_fails(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def gemini_down(prompt):
        raise requests.ConnectionError("Gemini is down")

    monkeypatch.setattr(classify, "LLMS", [
        ("gemini", "GEMINI_API_KEY", gemini_down),
        ("claude", "ANTHROPIC_API_KEY", lambda prompt: (ANSWER, "claude-test")),
    ])
    label = classify.classify("https://site.example/", PAGE, [])
    assert label["method"] == "claude (claude-test)"
