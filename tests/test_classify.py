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
    label = classify.to_label("```json\n" + ANSWER + "\n```", "claude (test)", PAGE)
    assert label["relevant"] is True
    assert label["brands"] == ["Jackpot City"]  # spelling variants merged
    assert label["contact"] == "a@b.com"


@pytest.mark.parametrize("broken", [
    "{}",
    '{"site_type": "casino", "relevant": "false", "brands": [], "contact": "", "reason": ""}',
    '{"site_type": "casino", "relevant": true, "brands": [], "contact": "", "reason": ""}',
    '{"site_type": "blog", "relevant": false, "brands": [], "contact": "", "reason": ""}',
    '{"site_type": "review", "relevant": true, "brands": "Betway", "contact": "", "reason": ""}',
])
def test_broken_answer_is_an_error(broken):
    with pytest.raises(ValueError):
        classify.to_label(broken, "gemini (test)", PAGE)


def test_broken_answer_is_not_saved_as_llm_label(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(classify, "LLMS", [("gemini", "GEMINI_API_KEY", lambda prompt: ("{}", "test"))])
    label = classify.classify("https://site.example/", PAGE, [])
    assert label["method"] == "rules"  # rules labels are re-checked by the LLM on the next run


def test_invented_contact_is_replaced_by_one_from_the_page():
    answer = ANSWER.replace('"contact": "a@b.com"', '"contact": "https://site.example/visit/stake/"')
    assert classify.to_label(answer, "gemini (test)", PAGE)["contact"] == "a@b.com"  # found on the page
    no_candidates = {**PAGE, "emails": []}
    assert classify.to_label(answer, "gemini (test)", no_candidates)["contact"] == ""


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
    assert label["method"].startswith("claude (claude-test)")


def test_slot_games_are_not_brands():
    answer = ANSWER.replace('"Jackpot City Casino"', '"Mega Moolah", "Gladiator Jackpot"')
    assert classify.to_label(answer, "gemini (test)", PAGE)["brands"] == ["Jackpot City"]


def test_operator_subdomain_is_not_a_placement_site(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    blog = ANSWER.replace('"Jackpot City", "Jackpot City Casino"', '"WinSpirit", "Rocketplay Casino"')
    monkeypatch.setattr(classify, "LLMS", [("gemini", "GEMINI_API_KEY", lambda prompt: (blog, "test"))])
    label = classify.classify("https://blog.rocketplay.com/", PAGE, [])
    assert (label["relevant"], label["site_type"], label["brands"][0]) == (False, "casino", "Rocketplay Casino")


def test_operator_keeps_its_own_brand(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    casino = '{"site_type": "casino", "relevant": false, "brands": [], "contact": "", "reason": "Operator"}'
    monkeypatch.setattr(classify, "LLMS", [("gemini", "GEMINI_API_KEY", lambda prompt: (casino, "test"))])
    label = classify.classify("https://www.playojo.com/ca/", PAGE, ["PlayOJO"])
    assert label["brands"] == ["PlayOJO"]


def test_brand_inside_a_longer_domain_word_is_not_an_operator():
    from serp_mvp import rules
    assert rules.operator_brand("https://casinodays-review.com/", ["Casino Days"]) is None
