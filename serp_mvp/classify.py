"""Step 3: label a site with an LLM. Tries every LLM that has a key in .env, in order:
Gemini -> Claude -> OpenAI. If none has a key, or all of them fail, simple rules decide."""
import json
import logging
import os

import requests

import config
from serp_mvp import rules
from serp_mvp.retry import with_retries

log = logging.getLogger(__name__)

PROMPT = """You help an online-casino affiliate team find websites where they can place their casino brands.

Look at the web page below and answer in JSON with exactly these fields:
- "site_type": one of "review" (casino reviews, rankings, bonus lists, comparison sites),
  "casino" (the website of a casino operator itself), "wiki", "news", "forum", "regulator", "other".
- "relevant": true only for "review" sites. Casino operators, Wikipedia, forums, news and regulators are false.
- "brands": every real-money online-casino operator mentioned on the page (empty list if none), e.g.
  "Jackpot City", "Spin Casino". Go through all rankings, tables and bonus cards; brands often appear only as
  logos, written in the text as [image: ...]. NOT slot or game titles, game providers, payment methods,
  sportsbooks without a casino, prediction markets (e.g. Polymarket), free-to-play or social games and
  free poker apps (e.g. Cosmo Spins, Replay Poker). Each brand once.
- "contact": an email or contact-page URL for reaching the site owner about advertising. Use ONLY the
  candidates given below, never invent one. Prefer advertising / partnership contacts, then a general
  contact; never a careers page or a personal author email if a general one exists. Empty string if none.
- "reason": one short sentence explaining the decision.

Answer with the JSON object only, no other text.

URL: {url}
Title: {title}
Emails found on the page: {emails}
Contact-like links found on the page: {contact_links}
Page text (truncated):
{text}
"""


def ask_gemini(prompt):
    model = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"
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
    return response.json()["candidates"][0]["content"]["parts"][0]["text"], model


def ask_claude(prompt):
    model = os.getenv("CLAUDE_MODEL") or "claude-haiku-5-5"
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.getenv("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
        json={"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"], model


def ask_openai(prompt):
    model = os.getenv("OPENAI_MODEL") or "gpt-5-mini"
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "response_format": {"type": "json_object"}},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"], model


SITE_TYPES = ("review", "casino", "wiki", "news", "forum", "regulator", "other")

# (name, key in .env, function) - in the order they are tried
LLMS = [
    ("gemini", "GEMINI_API_KEY", ask_gemini),
    ("claude", "ANTHROPIC_API_KEY", ask_claude),
    ("openai", "OPENAI_API_KEY", ask_openai),
]


def available_llms():
    return [(name, ask) for name, key, ask in LLMS if os.getenv(key)]


def llm_available():
    return bool(available_llms())


def classify(url, page, brands):
    # Without the page text the LLM has nothing to read, so rules decide.
    if page is None:
        return rules.classify(url, page, brands)
    prompt = PROMPT.format(
        url=url,
        title=page["title"],
        emails=", ".join(page["emails"]) or "none",
        contact_links=", ".join(page["contact_links"]) or "none",
        text=page["text"],
    )
    for name, ask in available_llms():
        try:
            text, model = with_retries(lambda: ask(prompt), attempts=3, first_pause=10)
            return to_label(text, f"{name} ({model}), {config.LABEL_VERSION}", page)
        except Exception as error:
            log.warning("%s failed for %s (%s), trying the next option", name, url, error)
    return rules.classify(url, page, brands)


def to_label(text, method, page):
    """Turn the LLM's JSON answer into our label. A broken answer raises an error, so it is retried or the
    next LLM / the rules decide; it is never saved as a finished label."""
    answer = json.loads(text[text.find("{"):text.rfind("}") + 1])  # Claude may wrap JSON in ```json ... ```
    if answer.get("site_type") not in SITE_TYPES:
        raise ValueError(f"site_type is {answer.get('site_type')!r}")
    if not isinstance(answer.get("relevant"), bool):  # "false" as a string would count as true
        raise ValueError(f"relevant is {answer.get('relevant')!r}, not true/false")
    if answer["relevant"] != (answer["site_type"] == "review"):
        raise ValueError("relevant does not match site_type")
    if not isinstance(answer.get("brands"), list) or not all(isinstance(b, str) for b in answer["brands"]):
        raise ValueError("brands is not a list of names")

    # The contact must be one of the candidates found on the page; anything else is dropped.
    contact = answer.get("contact") or ""
    if contact not in page["emails"] + page["contact_links"]:
        contact = ""

    # The LLM sometimes repeats a brand in different spellings ("Jackpot City" / "Jackpot City Casino").
    brands = {}
    for brand in answer.get("brands", []):
        brands.setdefault(rules.brand_key(brand), brand.strip())

    return {
        "relevant": bool(answer.get("relevant")),
        "site_type": answer.get("site_type", "other"),
        "brands": list(brands.values()),
        "contact": contact,
        "reason": str(answer.get("reason", "")),
        "method": method,
    }
