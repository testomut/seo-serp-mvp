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
CONTACT_WORDS = ("contact", "advertise with us", "write for us", "work with us")
# Affiliate redirects to a casino ("/visit/stake/") are not the site owner's contact
AFFILIATE_PATHS = ("/visit/", "/go/", "/out/", "/goto/", "/recommends/", "/refer/", "/click")


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


def parse(url, html):
    soup = BeautifulSoup(html, "html.parser")

    contact_links = []
    emails = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("mailto:"):
            emails.append(href.removeprefix("mailto:").split("?")[0])
        elif any(word in link.get_text().lower() for word in CONTACT_WORDS) or "/contact" in href.lower():
            full_url = urljoin(url, href)
            # Only the site's own pages, never a redirect to a casino
            if domain_of(full_url) == domain_of(url) and not any(p in full_url.lower() for p in AFFILIATE_PATHS):
                contact_links.append(full_url)

    # Emails are taken only from visible text and mailto links, not from scripts
    # (scripts contain technical addresses like error-tracker keys).
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    emails += EMAIL_RE.findall(text)
    emails = [e for e in dict.fromkeys(emails) if not e.endswith((".png", ".jpg", ".webp", ".svg"))]

    return {
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "text": text[: config.PAGE_TEXT_LIMIT],
        "emails": emails[:5],
        "contact_links": list(dict.fromkeys(contact_links))[:5],
    }
