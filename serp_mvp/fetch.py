"""Step 2: download a page and pull out what the classifier needs."""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config
from serp_mvp.retry import with_retries
from serp_mvp.rules import domain_of

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "en-CA,en;q=0.9",
}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Contact links, best first: advertising / partnerships, then a general contact page
CONTACT_WORDS = [("advertis", "partner", "affiliate"), ("contact", "write for us", "work with us")]
NOT_CONTACT_WORDS = ("career", "jobs", "vacanc")  # hiring pages are not a channel for placements
# Affiliate redirects to a casino ("/visit/stake/") are not the site owner's contact
AFFILIATE_PATHS = ("/visit/", "/go/", "/out/", "/goto/", "/recommends/", "/refer/", "/click")
# Some sites answer 200 with a "not available in your country" page instead of the content
GEO_BLOCK_PHRASES = ("not available in your country", "not available in your region", "country is restricted",
                     "restricted in your country", "not accessible from your country", "country-blocked",
                     "your jurisdiction", "your location is not")


def get_page(url):
    """Return {"title", "text", "emails", "contact_links"}, or None if the page can't be loaded."""
    try:
        html = with_retries(lambda: download(url), attempts=2)
    except Exception:
        return None
    return parse(url, html)


def download(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def contact_priority(link_text, href):
    """0 = advertising/partnerships, 1 = general contact, None = not a contact link."""
    words = (link_text + " " + href).lower()
    if any(word in words for word in NOT_CONTACT_WORDS):
        return None
    for priority, group in enumerate(CONTACT_WORDS):
        if any(word in words for word in group):
            return priority
    return None


def parse(url, html):
    soup = BeautifulSoup(html, "html.parser")

    contact_links = []  # (priority, url)
    emails = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("mailto:"):
            emails.append(href.removeprefix("mailto:").split("?")[0])
            continue
        priority = contact_priority(link.get_text(), href)
        full_url = urljoin(url, href)
        # Only the site's own pages, never a redirect to a casino
        if priority is not None and domain_of(full_url) == domain_of(url) \
                and not any(p in full_url.lower() for p in AFFILIATE_PATHS):
            contact_links.append((priority, full_url))
    contact_links = list(dict.fromkeys(link for _, link in sorted(contact_links)))

    # Emails are taken only from visible text and mailto links, not from scripts
    # (scripts contain technical addresses like error-tracker keys). Footer emails count too.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    emails += EMAIL_RE.findall(soup.get_text(" "))
    emails = [e for e in dict.fromkeys(emails) if not e.endswith((".png", ".jpg", ".webp", ".svg"))]

    # The LLM reads only the main part: menus, header and footer would fill the text limit
    for tag in soup(["nav", "header", "footer"]):
        tag.decompose()

    # Casino lists often show brands only as logos: keep the image description in the text,
    # once per page and not when the same words are already written next to the image
    seen = set()
    for image in soup.find_all("img", alt=True):
        alt = image["alt"].strip()
        nearby = image.parent.get_text(" ").lower() if image.parent else ""
        if 2 < len(alt) <= 60 and alt.lower() not in seen and alt.lower() not in nearby:
            seen.add(alt.lower())
            image.replace_with(f" [image: {alt}] ")
        else:
            image.replace_with(" ")
    text = " ".join(soup.get_text(" ").split())

    # A short page that says "not available in your country" has no content to label
    if len(text) < 3000 and any(phrase in text.lower() for phrase in GEO_BLOCK_PHRASES):
        return None

    return {
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "text": text[: config.PAGE_TEXT_LIMIT],
        "emails": emails[:5],
        "contact_links": contact_links[:5],
    }
