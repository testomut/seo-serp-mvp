"""Step 1: get Google results for a keyword.

Uses the first service that has a key in .env: SearchApi.io, then SerpApi.
Both have the same parameters and answer format. Without keys: demo data from data/sample_serp.json.
Every result is a dict: {"position": 1, "url": "...", "title": "..."}.
"""
import json
import os

import requests

import config
from serp_mvp.retry import with_retries

SERVICES = {
    # name: (env variable with the key, API address)
    "searchapi": ("SEARCHAPI_KEY", "https://www.searchapi.io/api/v1/search"),
    "serpapi": ("SERPAPI_KEY", "https://serpapi.com/search.json"),
}


def search(keyword):
    """Return (results, source) where source is "searchapi", "serpapi" or "sample"."""
    for name, (key_name, url) in SERVICES.items():
        if os.getenv(key_name):
            return with_retries(lambda: search_api(url, os.getenv(key_name), keyword)), name
    return search_sample(keyword), "sample"


def search_api(url, api_key, keyword):
    params = {
        "engine": "google",
        "q": keyword,
        "google_domain": config.GOOGLE_DOMAIN,
        "gl": config.COUNTRY,
        "hl": config.LANGUAGE,
        "device": config.DEVICE,
        "num": config.TOP_N,
        "api_key": api_key,
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])

    results = []
    for item in data.get("organic_results", []):
        results.append({"position": item["position"], "url": item["link"], "title": item.get("title", "")})
    return results[: config.TOP_N]


def search_sample(keyword):
    with open(config.SAMPLE_SERP_FILE, encoding="utf-8") as file:
        sample = json.load(file)
    return sample.get(keyword, [])
