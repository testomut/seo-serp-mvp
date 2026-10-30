from serp_mvp import storage

RESULTS = [
    {"position": 1, "url": "https://a.com/", "title": "A"},
    {"position": 2, "url": "https://b.com/", "title": "B"},
]


def count(db, table):
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_same_day_rerun_does_not_duplicate():
    db = storage.connect(":memory:")
    storage.save_positions(db, "2026-11-01", "kw", RESULTS, "sample")
    storage.save_positions(db, "2026-11-01", "kw", RESULTS, "sample")
    assert count(db, "positions") == 2


def test_next_day_adds_history():
    db = storage.connect(":memory:")
    storage.save_positions(db, "2026-11-01", "kw", RESULTS, "sample")
    storage.save_positions(db, "2026-11-02", "kw", RESULTS, "sample")
    assert count(db, "positions") == 4


def test_labelled_url_is_not_checked_again():
    db = storage.connect(":memory:")
    storage.save_positions(db, "2026-11-01", "kw", RESULTS, "sample")
    label = {"relevant": True, "site_type": "review", "brands": [], "contact": "", "reason": "", "method": "gemini"}
    storage.save_site(db, "https://a.com/", label)
    assert storage.urls_to_check(db, "2026-11-01", llm_available=True) == ["https://b.com/"]


def test_rules_labels_are_rechecked_when_llm_appears():
    db = storage.connect(":memory:")
    storage.save_positions(db, "2026-11-01", "kw", RESULTS[:1], "sample")
    label = {"relevant": False, "site_type": "other", "brands": [], "contact": "", "reason": "", "method": "rules"}
    storage.save_site(db, "https://a.com/", label)
    assert storage.urls_to_check(db, "2026-11-01", llm_available=False) == []
    assert storage.urls_to_check(db, "2026-11-01", llm_available=True) == ["https://a.com/"]
