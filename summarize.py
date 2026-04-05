import requests

import config
from email_processing import _get_sanitized_html_body
from parsers import parse_specialized_email_stories

_SYSTEM_PROMPT = (
    "You are a concise news summarizer. Given an article, produce a clear, "
    "informative summary in 3-5 sentences. Focus on the key facts and takeaways. "
    "Do not include any preamble like 'Here is a summary'. Just output the summary."
)

_SPLIT_SYSTEM_PROMPT = (
    "You split newsletter content into independent stories.\n"
    "Return ONLY valid JSON as an array.\n"
    "Each array item must be an object with keys: title, text.\n"
    "Rules:\n"
    "- Semantic HTML tags such as <h1>-<h6>, <section>, <article> may indicate story boundaries, but please check context.\n"
    "- Keep each story semantically independent.\n"
    "- Ignore boilerplate sections (ads, footer, unsubscribe).\n"
    "- Keep text faithful to source content; do not invent facts.\n"
    "- If there is only one story, return one item.\n"
    "- No markdown code fences, no explanations."
)


def _extract_json_array(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start:end + 1]


def _fallback_story_split(email_text, email_subject=""):
    title = (email_subject or "Email story").strip()
    return [{"title": title, "text": email_text.strip()}]


def split_email_stories(email, email_subject=""):
    """
    Split a content-heavy email into independent stories using Ollama.
    Returns list of dicts: [{title, text}, ...]
    Falls back to a single-story chunk on parse/model failures.
    """

    specialized_stories = parse_specialized_email_stories(email)
    if specialized_stories:
        print(f"  Using specialized parser for story splitting (subject: '{email_subject}').")
        return specialized_stories

    text = _get_sanitized_html_body(email)
    print(f"  Attempting to split email into stories with Ollama (subject: '{email_subject}') and content '{text}' words...")
    if not text:
        return []

    prompt = (
        f"Email subject: {email_subject or '(none)'}\n"
        f"Minimum words per story: {config.EMAIL_STORY_MIN_WORDS}\n"
        f"Preferred maximum words per story: {config.EMAIL_STORY_MAX_WORDS}\n\n"
        "Email content:\n"
        f"{text}"
    )

    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": config.OLLAMA_MODEL,
                "system": _SPLIT_SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1400},
            },
            timeout=180,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
        json_array_str = _extract_json_array(raw)
        if not json_array_str:
            return _fallback_story_split(text, email_subject=email_subject)

        import json

        parsed = json.loads(json_array_str)
        if not isinstance(parsed, list):
            return _fallback_story_split(text, email_subject=email_subject)

        stories = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            body = str(item.get("text", "")).strip()
            if not body:
                continue
            if len(body.split()) < config.EMAIL_STORY_MIN_WORDS:
                continue
            stories.append({
                "title": title or (email_subject or "Email story"),
                "text": body,
            })

        return stories or _fallback_story_split(text, email_subject=email_subject)
    except requests.ConnectionError:
        print("  ⚠️  Cannot connect to Ollama for story splitting. Using single story.")
        return _fallback_story_split(text, email_subject=email_subject)
    except requests.RequestException as e:
        print(f"  ⚠️  Story splitting request failed: {e}. Using single story.")
        return _fallback_story_split(text, email_subject=email_subject)
    except ValueError as e:
        print(f"  ⚠️  Story splitting JSON parse failed: {e}. Using single story.")
        return _fallback_story_split(text, email_subject=email_subject)


def summarize(article_text, title=""):
    """
    Summarize an article using the local Ollama model.
    Returns the summary string, or a fallback on failure.
    """
    prompt = f"Article title: {title}\n\n{article_text}"

    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": config.OLLAMA_MODEL,
                "system": _SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 300},
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.ConnectionError:
        print("  ⚠️  Cannot connect to Ollama. Is it running? (ollama serve)")
        return _fallback_summary(article_text)
    except Exception as e:
        print(f"  ⚠️  Summarization error: {e}")
        return _fallback_summary(article_text)


def summarize_extended(article_text, title=""):
    """
    Produce a ~3-minute summary (~450 words) for long articles.
    Used when the article exceeds the configured word limit.
    """
    system_prompt = (
        "You are a thorough news summarizer. Given an article, produce a detailed "
        "summary of approximately 450 words (about 3 minutes when read aloud). "
        "Cover all the key points, arguments, and conclusions. "
        "Do not include any preamble like 'Here is a summary'. Just output the summary."
    )
    prompt = f"Article title: {title}\n\n{article_text}"

    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": config.OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 800},
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.ConnectionError:
        print("  ⚠️  Cannot connect to Ollama. Is it running? (ollama serve)")
        return _fallback_extended_summary(article_text)
    except Exception as e:
        print(f"  ⚠️  Extended summarization error: {e}")
        return _fallback_extended_summary(article_text)


def _fallback_summary(text):
    """Simple extractive fallback: first 3 sentences."""
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:3])


def _fallback_extended_summary(text):
    """Extractive fallback: first ~450 words."""
    words = text.split()
    return " ".join(words[:450])
