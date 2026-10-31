"""Labelling without an LLM: simple, predictable rules. Used when GEMINI_API_KEY is not set
or the LLM call fails. Less accurate than the LLM, so every row records which method was used."""
import re
from collections import Counter
from urllib.parse import urlparse

import config

NOT_RELEVANT_DOMAINS = (
    "wikipedia.org", "youtube.com", "reddit.com", "facebook.com", "x.com", "instagram.com",
    "canada.ca", "gc.ca", "agco.ca", "igamingontario.ca",
)
REVIEW_WORDS = ("best", "top", "review", "rating", "ranking", "compare", "bonus", "free spins", "no deposit")


def load_brands(path=None):
    with open(path or config.BRANDS_FILE, encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip() and not line.startswith("#")]


def operator_brand(url, brands):
    """The brand whose own site this is, or None. "blog.rocketplay.com" + "Rocketplay Casino" -> that brand.
    A part of the domain must equal the whole brand name, so "casinodays-review.com" doesn't count."""
    parts = domain_of(url).split(".")
    for brand in brands:
        # "Rocketplay Casino" -> "rocketplaycasino" or "rocketplay"
        if re.sub(r"[^a-z0-9]", "", brand.lower()) in parts or brand_key(brand) in parts:
            return brand
    return None


def find_brands(text, brands):
    found = []
    for brand in brands:
        if re.search(r"\b" + re.escape(brand) + r"\b", text, re.IGNORECASE):
            found.append(brand)
    return found


def brand_key(name):
    """One key for all spellings of a brand: "Tonybet Casino", "TonyBet", "Toppz.ca" -> "tonybet", "tonybet", "toppz"."""
    name = re.sub(r"(\s+casino|\.com|\.ca)+$", "", name.strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def brand_names(brand_lists, known_brands):
    """Pick one spelling per brand: from brands.txt if it is there, otherwise the most frequent one."""
    names = {}
    for name, _ in Counter(b for brands in brand_lists for b in brands).most_common():
        names.setdefault(brand_key(name), name)
    names.update({brand_key(name): name for name in known_brands})
    return names


def domain_of(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def pick_contact(page):
    if page and page["emails"]:
        return page["emails"][0]
    if page and page["contact_links"]:
        return page["contact_links"][0]
    return ""


def classify(url, page, brands):
    domain = domain_of(url)
    text = (page["title"] + " " + page["text"]) if page else ""
    found = find_brands(text, brands)
    label = {"brands": found, "contact": pick_contact(page), "method": "rules"}

    if any(domain == d or domain.endswith("." + d) for d in NOT_RELEVANT_DOMAINS):
        return {**label, "relevant": False, "site_type": "other", "reason": "Known non-affiliate site"}

    # "jackpotcity.com" -> operator site of the Jackpot City brand
    brand = operator_brand(url, brands)
    if brand:
        return {**label, "brands": list(dict.fromkeys([brand] + found)), "relevant": False, "site_type": "casino",
                "reason": f"Domain belongs to brand {brand}"}

    if page is None:
        return {**label, "relevant": None, "site_type": "unknown", "reason": "Page could not be loaded"}

    has_review_words = any(word in text.lower()[:3000] for word in REVIEW_WORDS)
    if has_review_words and len(found) >= 2:
        return {**label, "relevant": True, "site_type": "review", "reason": "Review/ranking words and several brands"}

    return {**label, "relevant": False, "site_type": "other", "reason": "No signs of a review/ranking site"}
