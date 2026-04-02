import re

import config
from extract_links import extract_links_with_details


def _get_html_body(email):
    """Extract the HTML body from an email, if available."""
    html = email.get("html") or ""
    return html.strip()


def _get_sanitized_html_body(email):
    """
    Return HTML body with scripts/styles removed and tag attributes stripped.
    Keeps HTML tags and textual content.
    """
    html = _get_html_body(email)
    if not html:
        return ""

    # Remove script/style blocks entirely.
    body = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>", "", html)
    # Remove HTML comments.
    body = re.sub(r"(?is)<!--.*?-->", "", body)

    # Keep tags but drop all attributes.
    def _strip_tag_attributes(match):
        slash_open = match.group(1) or ""
        tag_name = match.group(2)
        slash_close = match.group(3) or ""
        return f"<{slash_open}{tag_name}{slash_close}>"

    body = re.sub(
        r"(?is)<\s*(/?)\s*([a-zA-Z][\w:-]*)\b[^>]*?(/?)\s*>",
        _strip_tag_attributes,
        body,
    )
    return body.strip()


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
