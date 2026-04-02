import requests

import config

_SYSTEM_PROMPT = (
    "You are a concise news summarizer. Given an article, produce a clear, "
    "informative summary in 3-5 sentences. Focus on the key facts and takeaways. "
    "Do not include any preamble like 'Here is a summary'. Just output the summary."
)


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
