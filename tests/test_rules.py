from serp_mvp import rules

BRANDS = ["Jackpot City", "Spin Casino", "Betway"]


def page(text, title=""):
    return {"title": title, "text": text, "emails": [], "contact_links": []}


def test_wikipedia_is_not_relevant():
    label = rules.classify("https://en.wikipedia.org/wiki/Online_casino", page("Jackpot City Betway"), BRANDS)
    assert label["relevant"] is False


def test_operator_site_is_not_relevant():
    label = rules.classify("https://www.jackpotcity.com/", page("Welcome to Jackpot City"), BRANDS)
    assert label["site_type"] == "casino"
    assert label["relevant"] is False


def test_review_site_is_relevant():
    text = "Best online casinos in Canada: Jackpot City, Spin Casino and Betway reviewed"
    label = rules.classify("https://casinoreviews.example/", page(text), BRANDS)
    assert label["relevant"] is True
    assert label["brands"] == BRANDS


def test_unloaded_page_is_unknown():
    label = rules.classify("https://some-site.example/", None, BRANDS)
    assert label["relevant"] is None
