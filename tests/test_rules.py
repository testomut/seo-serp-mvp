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


def test_brand_spellings_are_merged():
    assert rules.brand_key("Tonybet Casino") == rules.brand_key("TonyBet") == "tonybet"
    assert rules.brand_key("Hell Spin") == rules.brand_key("HellSpin Casino")
    names = rules.brand_names([["Tonybet Casino", "Hell Spin"], ["TonyBet"], ["TonyBet"]], ["HellSpin"])
    assert names["tonybet"] == "TonyBet"    # the most frequent spelling
    assert names["hellspin"] == "HellSpin"  # the spelling from brands.txt wins


def test_sports_products_become_casino_brands_only_when_listed():
    names = ["LeoVegas Sports", "LeoVegas", "888 Sports", "Unknown Sportsbook", "Sports Interaction", "Mega Moolah"]
    assert rules.clean_brands(names) == ["LeoVegas", "888casino", "Sports Interaction"]


def test_contact_priority():
    page = {"emails": ["carol.smith@site.com", "info@site.com"], "contact_links": ["https://site.com/contact/"]}
    assert rules.pick_contact(page) == "info@site.com"  # general beats author email
    page["contact_links"].append("https://site.com/advertise-with-us/")
    assert rules.pick_contact(page) == "https://site.com/advertise-with-us/"  # advertising beats general
    only_author = {"emails": ["carol.smith@site.com"], "contact_links": []}
    assert rules.pick_contact(only_author) == "carol.smith@site.com"  # author email when nothing else


def test_casino_without_space_is_merged():
    assert rules.brand_key("888casino") == rules.brand_key("888 Casino")
