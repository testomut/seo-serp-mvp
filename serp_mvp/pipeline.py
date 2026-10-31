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


def run(demo=False):
    """demo=True: sample results, separate demo database and Excel, no Google Sheet and no notifications."""
    if not demo and not serp.has_key():
        raise SystemExit("No search API key (SEARCHAPI_KEY or SERPAPI_KEY). To try without keys: python main.py --demo")
    today = date.today().isoformat()
    db = storage.connect(config.DEMO_DB_FILE if demo else config.DB_FILE)
    brands = rules.load_brands()
    llm = classify.llm_available()
    keywords = serp.sample_keywords() if demo else load_keywords()
    failed_keywords = []
    short_keywords = []  # fewer than 10 results: Google itself showed fewer
    new_relevant = []

    # Steps 1-2: Google results for every keyword
    for keyword in keywords:
        try:
            results, source = (serp.search_sample(keyword), "sample") if demo else serp.search(keyword)
        except Exception as error:
            log.error("Search failed for '%s': %s", keyword, error)
            storage.save_failed_search(db, today, keyword)
            failed_keywords.append(keyword)
            continue
        storage.save_positions(db, today, keyword, results, source)
        if len(results) < config.TOP_N:
            short_keywords.append(f"{keyword} ({len(results)})")
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
    excel_file = config.DEMO_EXCEL_FILE if demo else config.EXCEL_FILE
    storage.export_excel(db, excel_file)
    log.info("Saved %s", excel_file)
    if sheets.enabled() and not demo:
        sheets.write_results(db)
        log.info("Updated Google Sheet: %s", sheets.sheet_url())
    if failed_keywords:
        log.warning("Failed keywords (will be retried on the next run): %s", ", ".join(failed_keywords))

    # Step 5: notify
    status = "failed" if len(failed_keywords) == len(keywords) else "partial" if failed_keywords else "ok"
    if not demo:
        sheet_link = sheets.sheet_url() if sheets.enabled() else ""
        notify.send(notify.build_summary(today, status, len(keywords), failed_keywords, short_keywords,
                                         new_relevant, sheet_link))
    log.info("Done, status: %s", status)
    if status == "failed":
        raise SystemExit("All searches failed")  # non-zero exit code: the GitHub run turns red
