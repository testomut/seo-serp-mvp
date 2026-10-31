"""Step 1: get Google results for a keyword.

Tries every service that has a key in .env: SearchApi.io, then SerpApi (same parameters and answer format).
If all of them fail, the keyword fails; demo data from data/sample_serp.json is used only with --demo.
Every result is a dict: {"position": 1, "url": "...", "title": "..."}.
"""
import json
import logging
import os

import requests

import config
from serp_mvp.retry import with_retries

log = logging.getLogger(__name__)

SERVICES = {
    # name: (env variable with the key, API address, how to ask for page N)
    "searchapi": ("SEARCHAPI_KEY", "https://www.searchapi.io/api/v1/search", lambda page: {"page": page}),
    "serpapi": ("SERPAPI_KEY", "https://serpapi.com/search.json", lambda page: {"start": (page - 1) * 10}),
}
MAX_PAGES = 2


def has_key():
    return any(os.getenv(key_name) for key_name, _, _ in SERVICES.values())


def search(keyword):
    """Return (results, source). Raises if every configured service fails."""
    error = RuntimeError("No search API key: set SEARCHAPI_KEY or SERPAPI_KEY, or run with --demo")
    for name, (key_name, url, page_params) in SERVICES.items():
        if not os.getenv(key_name):
            continue
        try:
            return with_retries(lambda: search_api(url, os.getenv(key_name), page_params, keyword)), name
        except Exception as service_error:
            log.warning("%s failed for '%s' (%s), trying the next service", name, keyword, service_error)
            error = service_error
    raise error


def search_api(url, api_key, page_params, keyword):
    """Top-10 organic results. Google's mobile page often shows fewer than 10 (ads, app blocks,
    results removed by DMCA notices), so the next page is requested too. Position = organic rank 1..10."""
    results = []
    for page in range(1, MAX_PAGES + 1):
        try:
            organic = get_organic_results(url, api_key, page_params(page), keyword)
        except Exception as error:
            if page == 1:
                raise
            log.warning("Page %d failed for '%s' (%s), keeping %d results", page, keyword, error, len(results))
            break  # no next page: keep what the first page gave
        new = [r for r in organic if r["link"] not in {seen["url"] for seen in results}]
        results += [{"url": r["link"], "title": r.get("title", "")} for r in new]
        if len(results) >= config.TOP_N or not new:
            break
    return [{"position": number, **r} for number, r in enumerate(results[: config.TOP_N], start=1)]


def get_organic_results(url, api_key, extra_params, keyword):
    params = {
        "engine": "google",
        "q": keyword,
        "google_domain": config.GOOGLE_DOMAIN,
        "gl": config.COUNTRY,
        "hl": config.LANGUAGE,
        "device": config.DEVICE,
        "num": config.TOP_N,
        "api_key": api_key,
        **extra_params,
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    # A real answer always has search_metadata. Without it (e.g. "{}") it's a broken answer, not an empty Google page.
    if "search_metadata" not in data:
        raise RuntimeError("Unexpected answer from the search API")
    return data.get("organic_results", [])


def search_sample(keyword):
    with open(config.SAMPLE_SERP_FILE, encoding="utf-8") as file:
        sample = json.load(file)
    return sample.get(keyword, [])


def sample_keywords():
    with open(config.SAMPLE_SERP_FILE, encoding="utf-8") as file:
        return [keyword for keyword in json.load(file) if not keyword.startswith("_")]  # skip "_note"
