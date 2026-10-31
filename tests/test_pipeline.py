"""Whole-run checks with fake search results: no keys, no network, temporary files only."""
import pytest

import config
from serp_mvp import fetch, notify, pipeline, retry, serp, sheets, storage

RESULTS = [{"position": n, "url": f"https://site{n}.example/", "title": ""} for n in range(1, 11)]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """Temporary database and Excel files, no Sheet, no LLM, no pages, no pauses, no messages."""
    for name in ("DB_FILE", "DEMO_DB_FILE", "EXCEL_FILE", "DEMO_EXCEL_FILE"):
        monkeypatch.setattr(config, name, str(tmp_path / name))
    for key in ("SEARCHAPI_KEY", "SERPAPI_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(sheets, "enabled", lambda: False)
    monkeypatch.setattr(pipeline, "load_keywords", lambda: ["kw1", "kw2"])
    monkeypatch.setattr(fetch, "get_page", lambda url: None)
    monkeypatch.setattr(retry.time, "sleep", lambda seconds: None)
    sent = []
    monkeypatch.setattr(notify, "send", sent.append)
    return sent


def positions(path):
    return storage.connect(path).execute("SELECT COUNT(*) FROM positions").fetchone()[0]


def test_demo_does_not_touch_real_data(monkeypatch, isolated):
    monkeypatch.setenv("SEARCHAPI_KEY", "x")
    monkeypatch.setattr(serp, "search", lambda keyword: (RESULTS, "searchapi"))
    pipeline.run()
    assert positions(config.DB_FILE) == 20

    pipeline.run(demo=True)
    assert positions(config.DB_FILE) == 20      # real data untouched
    assert positions(config.DEMO_DB_FILE) > 0   # demo has its own database
    assert len(isolated) == 1                   # demo sends no notification


def test_no_search_key_stops_without_demo():
    with pytest.raises(SystemExit):
        pipeline.run()


def test_all_searches_failed_is_a_failed_run(monkeypatch, isolated):
    monkeypatch.setenv("SEARCHAPI_KEY", "x")

    def search_down(keyword):
        raise RuntimeError("down")

    monkeypatch.setattr(serp, "search", search_down)
    with pytest.raises(SystemExit):
        pipeline.run()
    assert "failed" in isolated[0]


def test_failed_search_shows_no_data_not_dropped_out():
    db = storage.connect(":memory:")
    storage.save_positions(db, "2026-11-01", "kw", RESULTS[:1], "searchapi")
    storage.save_failed_search(db, "2026-11-02", "kw")
    storage.save_positions(db, "2026-11-03", "kw", [], "searchapi")
    header, row = storage.positions_table(db)
    assert row[3:] == [1, "no data", ""]


def test_failure_later_the_same_day_keeps_good_results():
    db = storage.connect(":memory:")
    storage.save_positions(db, "2026-11-01", "kw", RESULTS, "searchapi")
    storage.save_failed_search(db, "2026-11-01", "kw")
    assert db.execute("SELECT status FROM searches").fetchone()[0] == "ok"


def test_broken_api_answer_is_an_error(monkeypatch):
    class Answer:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    monkeypatch.setattr(serp.requests, "get", lambda *args, **kwargs: Answer())
    with pytest.raises(RuntimeError):
        serp.search_api("https://api.example/", "x", lambda page: {"page": page}, "kw")


def test_second_search_service_is_used_when_first_fails(monkeypatch):
    monkeypatch.setenv("SEARCHAPI_KEY", "x")
    monkeypatch.setenv("SERPAPI_KEY", "y")
    monkeypatch.setattr(retry.time, "sleep", lambda seconds: None)

    def fake_search_api(url, api_key, page_params, keyword):
        if "searchapi" in url:
            raise RuntimeError("SearchApi is down")
        return RESULTS

    monkeypatch.setattr(serp, "search_api", fake_search_api)
    assert serp.search("kw") == (RESULTS, "serpapi")


def test_short_first_page_is_topped_up_from_the_next(monkeypatch):
    pages = {1: [{"link": "https://a.example/"}, {"link": "https://b.example/"}],
             2: [{"link": "https://b.example/"}, {"link": "https://c.example/"}]}
    monkeypatch.setattr(serp, "get_organic_results", lambda url, key, params, kw: pages[params["page"]])
    results = serp.search_api("https://api.example/", "x", lambda page: {"page": page}, "kw")
    assert [(r["position"], r["url"]) for r in results] == [
        (1, "https://a.example/"), (2, "https://b.example/"), (3, "https://c.example/")]


def test_affiliate_and_foreign_links_are_not_contacts():
    html = """<a href="/contact-us">Contact</a> <a href="/ca/visit/stake/">Contact Stake</a>
              <a href="https://casino.example/contact">Contact casino</a>"""
    page = fetch.parse("https://reviews.example/top/", html)
    assert page["contact_links"] == ["https://reviews.example/contact-us"]


def test_logos_contacts_and_geo_blocks():
    html = """<title>Top casinos</title><img alt="Lucky Tiger"> <img alt="">
              <a href="/careers/">Contact us about jobs</a> <a href="/contact/">Contact</a>
              <a href="/advertise/">Advertise with us</a>""" + "<p>text</p>" * 400
    page = fetch.parse("https://reviews.example/", html)
    assert "[image: Lucky Tiger]" in page["text"]
    assert page["contact_links"] == ["https://reviews.example/advertise/", "https://reviews.example/contact/"]
    assert fetch.parse("https://casino.example/", "<p>Sorry, this site is not available in your country.</p>") is None
    assert fetch.parse("https://casino.example/", "<p>Our website is restricted to visitors in your jurisdiction.</p>") is None
    menu = fetch.parse("https://reviews.example/", "<nav>Menu Betway</nav><main>Jackpot City review</main>")
    assert "Betway" not in menu["text"] and "Jackpot City" in menu["text"]  # menus are not page content
