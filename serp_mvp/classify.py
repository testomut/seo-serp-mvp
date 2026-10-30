"""Step 3: label a site. Gemini when GEMINI_API_KEY is set, otherwise (or on failure) simple rules."""
import json
import logging
import os

import requests

from serp_mvp import rules
from serp_mvp.retry import with_retries

log = logging.getLogger(__name__)

PROMPT = """You help an online-casino affiliate team find websites where they can place their casino brands.

Look at the web page below and answer in JSON with exactly these fields:
- "site_type": one of "review" (casino reviews, rankings, bonus lists, comparison sites),
  "casino" (the website of a casino operator itself), "wiki", "news", "forum", "regulator", "other".
- "relevant": true only for "review" sites. Casino operators, Wikipedia, forums, news and regulators are false.
- "brands": list of online-casino brand names mentioned on the page (empty list if none). Only casino
  operators (e.g. "Jackpot City", "Spin Casino"). NOT slot or game titles, game providers, payment methods,
  sportsbooks without a casino, or prediction markets. Each brand once.
- "contact": an email or contact-page URL for reaching the site owner. Use ONLY the candidates given below,
  never invent one. Empty string if there is none.
- "reason": one short sentence explaining the decision.

URL: {url}
Title: {title}
Emails found on the page: {emails}
Contact-like links found on the page: {contact_links}
Page text (truncated):
{text}
"""


def llm_available():
    return bool(os.getenv("GEMINI_API_KEY"))


def classify(url, page, brands):
    # Without the page text the LLM has nothing to read, so rules decide.
    if not llm_available() or page is None:
        return rules.classify(url, page, brands)
    try:
        return with_retries(lambda: ask_gemini(url, page), attempts=3, first_pause=10)
    except Exception as error:
        log.warning("LLM failed for %s (%s), falling back to rules", url, error)
        return rules.classify(url, page, brands)


def ask_gemini(url, page):
    model = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"
    prompt = PROMPT.format(
        url=url,
        title=page["title"],
        emails=", ".join(page["emails"]) or "none",
        contact_links=", ".join(page["contact_links"]) or "none",
        text=page["text"],
    )
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY")},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        },
        timeout=60,
    )
    response.raise_for_status()
    answer = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])

    # The LLM sometimes repeats a brand in different spellings ("Jackpot City" / "Jackpot City Casino").
    brands = {}
    for brand in answer.get("brands", []):
        brands.setdefault(rules.brand_key(brand), brand.strip())

    return {
        "relevant": bool(answer.get("relevant")),
        "site_type": answer.get("site_type", "other"),
        "brands": list(brands.values()),
        "contact": answer.get("contact", ""),
        "reason": answer.get("reason", ""),
        "method": f"gemini ({model})",
    }
