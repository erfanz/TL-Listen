import re
from html import unescape
from urllib.parse import urlparse

# Domains / patterns to skip
_SKIP_PATTERNS = [
    r"unsubscribe",
    r"manage.preferences",
    r"email-preferences",
    r"list-manage\.com",
    r"mailchimp\.com",
    r"tracking",
    r"click\.",
    r"mailto:",
    r"tel:",
    r"javascript:",
    r"\.png(\?|$)",
    r"\.jpg(\?|$)",
    r"\.gif(\?|$)",
    r"\.svg(\?|$)",
    r"\.css(\?|$)",
    r"fonts\.",
    r"favicon",
    r"apple\.com/app",
    r"play\.google\.com",
]

_SKIP_RE = re.compile("|".join(_SKIP_PATTERNS), re.IGNORECASE)

# Minimum URL length to consider (filters out short tracking redirects)
_MIN_URL_LEN = 30


def _extract_urls_from_html(html):
    """Pull href values from anchor tags."""
    return re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)


def _extract_urls_from_text(text):
    """Pull URLs from plain text."""
    return re.findall(r"https?://[^\s<>\"')\]]+", text)


def _is_article_url(url):
    """Heuristic: keep URLs that look like articles, skip junk."""
    if len(url) < _MIN_URL_LEN:
        return False
    if _SKIP_RE.search(url):
        return False
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http"):
        return False
    # Skip bare domain homepages
    if parsed.path in ("", "/") and not parsed.query:
        return False
    return True


def _clean_url(url):
    """Unescape HTML entities and strip tracking fragments."""
    url = unescape(url)
    # Remove common UTM parameters but keep the rest
    url = re.sub(r"[?&]utm_[^&]+", "", url)
    # Clean up leftover ? or & at end
    url = re.sub(r"[?&]$", "", url)
    return url


def extract_links(email):
    """
    Extract article URLs from an email dict {html, text}.
    Returns deduplicated list of URLs.
    """
    raw_urls = []
    if email.get("html"):
        raw_urls.extend(_extract_urls_from_html(email["html"]))
    if email.get("text"):
        raw_urls.extend(_extract_urls_from_text(email["text"]))

    seen = set()
    article_urls = []
    for url in raw_urls:
        url = _clean_url(url)
        if url in seen:
            continue
        seen.add(url)
        if _is_article_url(url):
            article_urls.append(url)

    return article_urls
