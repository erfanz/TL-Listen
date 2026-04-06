from html import unescape
import re
import unicodedata

_MOJIBAKE_MARKERS = ("Ã", "â", "ð", "�")
_EMOJI_JOINERS = {"\u200d", "\ufe0f"}


def repair_mojibake(text):
    """Repair common UTF-8-as-Latin-1 mojibake in titles and labels."""
    cleaned = unescape(str(text or "")).strip()
    if not cleaned:
        return ""
    if not any(marker in cleaned for marker in _MOJIBAKE_MARKERS):
        return cleaned

    try:
        repaired = cleaned.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return cleaned

    old_score = sum(cleaned.count(marker) for marker in _MOJIBAKE_MARKERS)
    new_score = sum(repaired.count(marker) for marker in _MOJIBAKE_MARKERS)
    return repaired if new_score < old_score else cleaned


def strip_emojis(text):
    """Remove emoji and related joiner characters from titles."""
    cleaned = []
    for char in str(text or ""):
        if char in _EMOJI_JOINERS:
            continue
        if unicodedata.category(char) == "So":
            continue
        cleaned.append(char)
    return re.sub(r"\s+", " ", "".join(cleaned)).strip()


def normalize_title(text):
    """Repair encoding issues and strip emoji from titles."""
    return strip_emojis(repair_mojibake(text))


def decode_http_text(response):
    """Decode HTTP text bodies more safely when servers omit charset headers."""
    content_type = (response.headers.get("content-type") or "").lower()
    encoding = (response.encoding or "").lower()

    if "charset=" in content_type and encoding and encoding != "iso-8859-1":
        return response.text
    if encoding and encoding != "iso-8859-1":
        return response.text

    for candidate in ("utf-8", getattr(response, "apparent_encoding", None), response.encoding):
        if not candidate:
            continue
        try:
            return response.content.decode(candidate, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue

    return response.content.decode("latin-1", errors="replace")
