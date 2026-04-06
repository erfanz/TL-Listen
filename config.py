import json
import os
import re
from copy import deepcopy
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = _PROJECT_ROOT / "config.json"

_DEFAULT_CONFIG = {
    "gmail": {
        "label": "digests",
        "credentials_file": "credentials.json",
        "token_file": "token.json",
        "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
    },
    "ollama": {
        "base_url": "http://localhost:11434",
        "model": "llama3.1",
    },
    "tts": {
        "voice": "af_heart",
        "speed": 1.0,
        "lang": "a",
    },
    "output": {
        "dir": "output",
        "link_skip_rules_file": "link_skip_rules.json",
    },
    "email_processing": {
        "force_content_subject_regex": [],
        "force_content_sender_regex": [],
        "force_links_subject_regex": [],
        "force_links_sender_regex": [],
        "content_min_words": 120,
        "content_max_link_density": 0.15,
        "story_min_words": 80,
        "story_max_words": 900,
        "content_parser_sender_rules": [],
        "link_parser_sender_rules": [],
    },
    "article_fetch": {
        "timeout": 30,
        "word_limit": 400,
    },
    "summarization": {
        "summary_sentence_count": 4,
        "summary_max_tokens": 300,
        "extended_summary_word_count": 450,
        "extended_summary_max_tokens": 800,
    },
    "ssl": {
        "ca_file": None,
    },
    "rss": {
        "feed_urls": [],
        "state_file": "rss_state.json",
        "output_dir": "output/rss",
        "fetch_timeout": 30,
        "initial_window_days": 7,
    },
}


def _deep_merge(base, overrides):
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_json_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing configuration file: {CONFIG_FILE}")
    data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{CONFIG_FILE} must contain a JSON object")
    return _deep_merge(_DEFAULT_CONFIG, data)


def _resolve_path(value):
    path = Path(value)
    if path.is_absolute():
        return path
    return _PROJECT_ROOT / path


def _load_regex_list(values, field_name):
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a JSON array of regex strings")
    regexes = []
    for idx, value in enumerate(values, 1):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}[{idx}] must be a non-empty string")
        regexes.append(value.strip())
    return regexes


def _load_parser_sender_rules(entries, field_name):
    if not isinstance(entries, list):
        raise ValueError(f"{field_name} must be a JSON array of rule objects")

    rules = []
    for idx, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"{field_name}[{idx}] must be an object")
        pattern = str(entry.get("pattern", "")).strip()
        parser_name = str(entry.get("parser", "")).strip()
        if not pattern or not parser_name:
            raise ValueError(
                f"{field_name}[{idx}] must include non-empty 'pattern' and 'parser' fields"
            )
        rules.append((re.compile(pattern, re.IGNORECASE), parser_name))
    return rules


_RAW_CONFIG = _load_json_config()

# Gmail settings
GMAIL_LABEL = str(_RAW_CONFIG["gmail"]["label"])
GMAIL_CREDENTIALS_FILE = _resolve_path(_RAW_CONFIG["gmail"]["credentials_file"])
GMAIL_TOKEN_FILE = _resolve_path(_RAW_CONFIG["gmail"]["token_file"])
GMAIL_SCOPES = list(_RAW_CONFIG["gmail"]["scopes"])

# Ollama settings
OLLAMA_BASE_URL = str(_RAW_CONFIG["ollama"]["base_url"])
OLLAMA_MODEL = str(_RAW_CONFIG["ollama"]["model"])

# TTS settings
TTS_VOICE = str(_RAW_CONFIG["tts"]["voice"])
TTS_SPEED = float(_RAW_CONFIG["tts"]["speed"])
TTS_LANG = str(_RAW_CONFIG["tts"]["lang"])

# Output settings
OUTPUT_DIR = _resolve_path(_RAW_CONFIG["output"]["dir"])
LINK_SKIP_RULES_FILE = _resolve_path(_RAW_CONFIG["output"]["link_skip_rules_file"])

# Email processing mode settings
email_processing = _RAW_CONFIG["email_processing"]
FORCE_CONTENT_SUBJECT_REGEX = _load_regex_list(
    email_processing["force_content_subject_regex"],
    "email_processing.force_content_subject_regex",
)
FORCE_CONTENT_SENDER_REGEX = _load_regex_list(
    email_processing["force_content_sender_regex"],
    "email_processing.force_content_sender_regex",
)
FORCE_LINKS_SUBJECT_REGEX = _load_regex_list(
    email_processing["force_links_subject_regex"],
    "email_processing.force_links_subject_regex",
)
FORCE_LINKS_SENDER_REGEX = _load_regex_list(
    email_processing["force_links_sender_regex"],
    "email_processing.force_links_sender_regex",
)
EMAIL_CONTENT_MIN_WORDS = int(email_processing["content_min_words"])
EMAIL_CONTENT_MAX_LINK_DENSITY = float(email_processing["content_max_link_density"])
EMAIL_STORY_MIN_WORDS = int(email_processing["story_min_words"])
EMAIL_STORY_MAX_WORDS = int(email_processing["story_max_words"])
CONTENT_PARSER_SENDER_RULES = _load_parser_sender_rules(
    email_processing["content_parser_sender_rules"],
    "email_processing.content_parser_sender_rules",
)
LINK_PARSER_SENDER_RULES = _load_parser_sender_rules(
    email_processing["link_parser_sender_rules"],
    "email_processing.link_parser_sender_rules",
)

# Article fetch settings
FETCH_TIMEOUT = int(_RAW_CONFIG["article_fetch"]["timeout"])
ARTICLE_WORD_LIMIT = int(_RAW_CONFIG["article_fetch"]["word_limit"])

# Summarization settings
SUMMARY_SENTENCE_COUNT = int(_RAW_CONFIG["summarization"]["summary_sentence_count"])
SUMMARY_MAX_TOKENS = int(_RAW_CONFIG["summarization"]["summary_max_tokens"])
EXTENDED_SUMMARY_WORD_COUNT = int(_RAW_CONFIG["summarization"]["extended_summary_word_count"])
EXTENDED_SUMMARY_MAX_TOKENS = int(_RAW_CONFIG["summarization"]["extended_summary_max_tokens"])

# SSL CA bundle (auto-detect Netskope or other corporate proxies)
_NETSKOPE_CERT = "/Library/Application Support/Netskope/STAgent/download/nscacert_combined.pem"
_default_ca = _NETSKOPE_CERT if os.path.exists(_NETSKOPE_CERT) else None
_configured_ssl_ca = _RAW_CONFIG["ssl"].get("ca_file")
SSL_CA_FILE = str(_resolve_path(_configured_ssl_ca)) if _configured_ssl_ca else _default_ca

# RSS settings
RSS_FEED_URLS = [
    str(url).strip()
    for url in _RAW_CONFIG["rss"]["feed_urls"]
    if str(url).strip()
]
RSS_STATE_FILE = _resolve_path(_RAW_CONFIG["rss"]["state_file"])
RSS_OUTPUT_DIR = _resolve_path(_RAW_CONFIG["rss"]["output_dir"])
RSS_FETCH_TIMEOUT = int(_RAW_CONFIG["rss"]["fetch_timeout"])
RSS_INITIAL_WINDOW_DAYS = int(_RAW_CONFIG["rss"]["initial_window_days"])
