import re

from bs4 import BeautifulSoup
from bs4.element import Tag

import config
from email_processing import _get_sanitized_html_body

_NON_STORY_TITLES = {
    "snacks shots",
}

_SKIPPED_LINK_ONLY_TEXTS = {
    "read more",
    "read the full report →",
    "google maps vs. apple maps",
}


def _normalize_story_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r"([,;:?!])([A-Za-z0-9\"'“‘])", r"\1 \2", text)
    return re.sub(r"(?<!\d)\.([A-Za-z\"'“‘])", r". \1", text)


def _normalize_heading_key(text):
    return (
        (text or "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .strip()
        .lower()
    )


def _extract_story_heading_title(tag):
    if not isinstance(tag, Tag) or tag.name != "h1":
        return None

    strong = tag.find("strong")
    if strong is None:
        return None

    link = tag.find("a")
    if link is not None and not link.find("strong"):
        return None

    title = _normalize_story_text(tag.get_text(" ", strip=True))
    if (
        not title
        or title.endswith(":")
        or _is_story_subheading(title)
        or _normalize_heading_key(title) in _NON_STORY_TITLES
    ):
        return None

    return title


def _is_link_only_paragraph(tag):
    if not isinstance(tag, Tag) or tag.name != "p":
        return False
    links = tag.find_all("a")
    if not links:
        return False
    paragraph_text = _normalize_story_text(tag.get_text(" ", strip=True))
    link_text = _normalize_story_text(" ".join(link.get_text(" ", strip=True) for link in links))
    return bool(paragraph_text) and paragraph_text == link_text


def _should_skip_link_only_paragraph(text):
    normalized = _normalize_heading_key(text)
    return normalized in _SKIPPED_LINK_ONLY_TEXTS


def _is_boilerplate(tag_text):
    return (
        tag_text.startswith("*Event contracts are offered through Robinhood Derivatives")
        or tag_text.startswith("Indexes are not directly investable.")
        or tag_text.startswith("Advertiser's disclosures:")
        or tag_text.startswith("Sherwood Media, LLC produces fresh and unique perspectives")
        or tag_text.startswith("Was this email forwarded to you?")
        or tag_text.startswith("Craving more insights in your inbox")
    )


def _is_story_subheading(heading_text):
    normalized = heading_text.replace("“", "").replace("”", "").replace("’", "'")
    return normalized.isupper()


def parse_robinhood_email_stories(email):
    print(f"Parsing Robinhood email with subject: {email.get('Subject', '')}")
    html = _get_sanitized_html_body(email)
    if not html:
        return []

    stories = []
    current_story = None

    def _finalize_current_story():
        if current_story is None:
            return
        story_text = "\n\n".join(current_story["blocks"]).strip()
        if not story_text:
            return
        stories.append({"title": current_story["title"], "text": story_text})

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["h1", "p", "ul", "ol"]):
        if tag.name == "h1":
            title = _extract_story_heading_title(tag)
            if title:
                _finalize_current_story()
                current_story = {"title": title, "blocks": []}
                continue

            if current_story is None:
                continue

            heading_text = _normalize_story_text(tag.get_text(" ", strip=True))
            if _is_story_subheading(heading_text):
                continue

            _finalize_current_story()
            current_story = None
            continue

        if current_story is None:
            continue

        if tag.name == "p":
            block_text = _normalize_story_text(tag.get_text(" ", strip=True))
            if _is_link_only_paragraph(tag) and _should_skip_link_only_paragraph(block_text):
                continue
            if not block_text or _is_boilerplate(block_text):
                continue
            current_story["blocks"].append(block_text)
            continue

        items = []
        for item in tag.find_all("li", recursive=False):
            item_text = _normalize_story_text(item.get_text(" ", strip=True))
            if item_text:
                items.append(f"- {item_text}")
        if items:
            current_story["blocks"].append("\n".join(items))

    _finalize_current_story()

    return stories
