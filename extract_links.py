import re
import json
from html import unescape
from urllib.parse import urlparse

import config

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


def _load_skip_rules():
    """
    Load user-configurable URL skip rules from JSON.
    Each rule supports:
      - domain (optional): exact host match, without/with www
      - path_regex (optional): regex matched against URL path
      - query_regex (optional): regex matched against URL query
    """
    path = config.LINK_SKIP_RULES_FILE
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of rule objects")
    rules = []
    for idx, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"{path} rule #{idx} must be an object")
        rule = {
            "domain": (item.get("domain") or "").lower().removeprefix("www."),
            "path_re": re.compile(item["path_regex"]) if item.get("path_regex") else None,
            "query_re": re.compile(item["query_regex"]) if item.get("query_regex") else None,
        }
        if not rule["domain"] and not rule["path_re"] and not rule["query_re"]:
            raise ValueError(
                f"{path} rule #{idx} must define at least one of domain, "
                "path_regex, query_regex"
            )
        rules.append(rule)
    return rules


_USER_SKIP_RULES = _load_skip_rules()


def _matches_user_skip_rule(parsed):
    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path or ""
    query = parsed.query or ""
    for rule in _USER_SKIP_RULES:
        if rule["domain"] and rule["domain"] != domain:
            continue
        if rule["path_re"] and not rule["path_re"].search(path):
            continue
        if rule["query_re"] and not rule["query_re"].search(query):
            continue
        return True
    return False


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
    if _matches_user_skip_rule(parsed):
        return False
    # Skip bare domain homepages
    if parsed.path in ("", "/") and not parsed.query:
        return False
    return True


def _classify_url(url):
    """Classify URL as article/not-article and return (is_article, reason)."""
    if len(url) < _MIN_URL_LEN:
        return False, "too_short"
    if _SKIP_RE.search(url):
        return False, "skip_pattern"
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http"):
        return False, "non_http"
    if _matches_user_skip_rule(parsed):
        return False, "skip_rule"
    if parsed.path in ("", "/") and not parsed.query:
        return False, "homepage"
    return True, "article"


def _clean_url(url):
    """Unescape HTML entities and strip tracking fragments."""
    url = unescape(url)
    # Remove common UTM parameters but keep the rest
    url = re.sub(r"[?&]utm_[^&]+", "", url)
    # Clean up leftover ? or & at end
    url = re.sub(r"[?&]$", "", url)
    return url


def extract_links_with_details(email):
    """
    Extract article URLs from an email dict {html, text}.
    Returns extraction details including kept/skipped URLs.
    """
    raw_urls = []
    if email.get("html"):
        raw_urls.extend(_extract_urls_from_html(email["html"]))
    if email.get("text"):
        raw_urls.extend(_extract_urls_from_text(email["text"]))

    seen = set()
    article_urls = []
    skipped_urls = []
    for url in raw_urls:
        url = _clean_url(url)
        if url in seen:
            skipped_urls.append({"url": url, "reason": "duplicate_in_email"})
            continue
        seen.add(url)
        is_article, reason = _classify_url(url)
        if is_article:
            article_urls.append(url)
        else:
            skipped_urls.append({"url": url, "reason": reason})

    return {
        "article_urls": article_urls,
        "skipped_urls": skipped_urls,
        "raw_count": len(raw_urls),
        "unique_cleaned_count": len(seen),
    }


def extract_links(email):
    """
    Extract article URLs from an email dict {html, text}.
    Returns deduplicated list of URLs.
    """
    details = extract_links_with_details(email)
    return details["article_urls"]
