"""The whole run, step by step: search -> save positions -> download pages -> label -> export -> notify."""
import csv
import logging
import time
from datetime import date

import config
from serp_mvp import classify, fetch, notify, rules, serp, sheets, storage

log = logging.getLogger(__name__)


def load_keywords():
    """Keywords from the Google Sheet if it's connected, otherwise from keywords.csv."""
    if sheets.enabled():
        return sheets.read_keywords()
    with open(config.KEYWORDS_FILE, encoding="utf-8") as file:
        return [row["keyword"] for row in csv.DictReader(file) if row["active"].strip().lower() == "yes"]


def run():
    today = date.today().isoformat()
    db = storage.connect(config.DB_FILE)
    brands = rules.load_brands()
    llm = classify.llm_available()
    keywords = load_keywords()
    failed_keywords = []
    new_relevant = []

    # Steps 1-2: Google results for every keyword
    for keyword in keywords:
        try:
            results, source = serp.search(keyword)
        except Exception as error:
            log.error("Search failed for '%s': %s", keyword, error)
            failed_keywords.append(keyword)
            continue
        storage.save_positions(db, today, keyword, results, source)
        log.info("'%s': %d results (%s)", keyword, len(results), source)

    # Step 3: label URLs we haven't seen yet
    urls = storage.urls_to_check(db, today, llm)
    log.info("%d new URLs to label (%s)", len(urls), " -> ".join(name for name, _ in classify.available_llms()) or "rules, no LLM key")
    for number, url in enumerate(urls, start=1):
        page = fetch.get_page(url)
        label = classify.classify(url, page, brands)
        storage.save_site(db, url, label)
        if label["relevant"]:
            new_relevant.append((url, label))
        log.info("[%d/%d] %s -> relevant=%s (%s)", number, len(urls), url, label["relevant"], label["method"])
        if llm and page is not None:
            time.sleep(config.LLM_PAUSE_SECONDS)

    # Step 4: export
    storage.export_excel(db, config.EXCEL_FILE)
    log.info("Saved %s", config.EXCEL_FILE)
    if sheets.enabled():
        sheets.write_results(db)
        log.info("Updated Google Sheet: %s", sheets.sheet_url())
    if failed_keywords:
        log.warning("Failed keywords (will be retried on the next run): %s", ", ".join(failed_keywords))

    # Step 5: notify
    sheet_link = sheets.sheet_url() if sheets.enabled() else ""
    notify.send(notify.build_summary(today, len(keywords), failed_keywords, new_relevant, sheet_link))
    log.info("Done.")
