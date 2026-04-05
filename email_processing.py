import re

from bs4 import BeautifulSoup, Comment
from bs4.element import NavigableString

import config
from extract_links import extract_links_with_details

_UNWRAP_TAGS_FOR_LLM = ("div", "table", "tbody", "tr", "td")


def _get_html_body(email):
    """Extract the HTML body from an email, if available."""
    html = email.get("html") or ""
    return html.strip()


def trim_html_for_llm(html, unwrap_tags=_UNWRAP_TAGS_FOR_LLM):
    """
    Trim HTML for downstream LLM use.
    Removes scripts/styles entirely, unwraps layout-only tags, strips comments,
    and drops attributes from remaining tags.
    """
    html = (html or "").strip()
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(("script", "style")):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag_name in unwrap_tags:
        for tag in soup.find_all(tag_name):
            tag.unwrap()

    for tag in soup.find_all(True):
        tag.attrs = {}

    for text_node in soup.find_all(string=True):
        if isinstance(text_node, NavigableString) and not text_node.strip():
            text_node.extract()

    while True:
        empty_tags = [
            tag
            for tag in soup.find_all(True)
            if not tag.get_text(strip=True) and not tag.find(True)
        ]
        if not empty_tags:
            break
        for tag in empty_tags:
            tag.decompose()

    return str(soup).strip()


def _get_sanitized_html_body(email):
    """
    Return trimmed HTML body for LLM input while preserving meaningful content.
    """
    return trim_html_for_llm(_get_html_body(email))


def _plain_email_content(email):
    """Build plain content from an email body for summarization."""
    text = (email.get("text") or "").strip()
    if text:
        return text

    html = email.get("html") or ""
    if not html:
        return ""

    # Preserve block boundaries before stripping tags to keep story structure.
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    body = re.sub(
        r"(?i)</?(p|div|br|li|h[1-6]|tr|section|article|blockquote)[^>]*>",
        "\n",
        body,
    )
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = re.sub(r"\n\s*\n\s*\n+", "\n\n", body)
    body = re.sub(r"[ \t]+", " ", body)
    return body.strip()


def _matches_any_regex(value, patterns):
    for pattern in patterns:
        if re.search(pattern, value, flags=re.IGNORECASE):
            return True
    return False


def _decide_email_mode(email):
    """
    Decide whether an email should be processed as:
      - links: fetch external article links
      - content: summarize stories in the email body itself
    """
    subject = email.get("subject", "")
    sender = email.get("from", "")

    if _matches_any_regex(subject, config.FORCE_CONTENT_SUBJECT_REGEX) or _matches_any_regex(
        sender, config.FORCE_CONTENT_SENDER_REGEX
    ):
        return "content", "forced_content_rule", None
    if _matches_any_regex(subject, config.FORCE_LINKS_SUBJECT_REGEX) or _matches_any_regex(
        sender, config.FORCE_LINKS_SENDER_REGEX
    ):
        return "links", "forced_links_rule", None

    body = _plain_email_content(email)
    words = len(body.split())
    link_details = extract_links_with_details(email)
    candidate_links = len(link_details["article_urls"])
    link_density = candidate_links / max(words, 1)

    is_content_email = (
        words >= config.EMAIL_CONTENT_MIN_WORDS
        and link_density <= config.EMAIL_CONTENT_MAX_LINK_DENSITY
    )
    mode = "content" if is_content_email else "links"
    reason = (
        f"heuristic(words={words}, links={candidate_links}, density={link_density:.4f})"
    )
    return mode, reason, link_details
