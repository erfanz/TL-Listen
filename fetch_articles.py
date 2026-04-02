import json
from urllib.parse import urlparse

import requests
import trafilatura

import config

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Domains that require JS rendering and can't be reliably scraped
_JS_ONLY_DOMAINS = {
    "x.com",
    "twitter.com",
    "instagram.com",
    "facebook.com",
    "threads.net",
    "linkedin.com",
}


def _resolve_url(url):
    """Follow redirects and return the final URL."""
    try:
        resp = requests.head(
            url,
            allow_redirects=True,
            timeout=config.FETCH_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        return resp.url
    except requests.RequestException:
        try:
            resp = requests.get(
                url,
                allow_redirects=True,
                timeout=config.FETCH_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
                stream=True,
            )
            resp.close()
            return resp.url
        except requests.RequestException:
            return url


def _download(url):
    """Download page HTML using requests (more reliable than trafilatura's fetcher)."""
    resp = requests.get(
        url,
        timeout=config.FETCH_TIMEOUT,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html,*/*"},
    )
    resp.raise_for_status()
    return resp.text


def _extract_title(html):
    """Extract title using trafilatura metadata, falling back to <title> tag."""
    try:
        meta = trafilatura.extract_metadata(html)
        if meta and meta.title:
            return meta.title
    except Exception:
        pass
    import re
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _is_js_only(url):
    """Check if the URL points to a JS-only site we can't scrape."""
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return domain in _JS_ONLY_DOMAINS


def fetch_article(url):
    """
    Fetch a URL and extract the main article text.
    Follows redirects before fetching. Skips JS-only sites.
    Returns dict: {url, title, text} or None on failure.
    """
    try:
        # Resolve redirect chains (e.g. newsletter tracking links)
        resolved = _resolve_url(url)
        if resolved != url:
            print(f"  ↪ Redirected to: {resolved}")

        if _is_js_only(resolved):
            print(f"  ⚠️  Skipping JS-only site: {resolved}")
            return None

        html = _download(resolved)
        if not html:
            print(f"  ⚠️  Empty response from: {resolved}")
            return None

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not text or len(text.strip()) < 100:
            print(f"  ⚠️  No substantial text extracted from: {resolved}")
            return None

        title = _extract_title(html)

        return {
            "url": resolved,
            "original_url": url,
            "title": title or "Untitled",
            "text": text.strip(),
        }

    except Exception as e:
        print(f"  ⚠️  Error fetching {url}: {e}")
        return None
