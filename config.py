import os
from pathlib import Path

from dotenv import load_dotenv

# Load project-level env vars from .env on startup.
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")

# Gmail settings
GMAIL_LABEL = os.getenv("DIGEST_GMAIL_LABEL", "digests")
GMAIL_CREDENTIALS_FILE = os.getenv("DIGEST_GMAIL_CREDENTIALS", "credentials.json")
GMAIL_TOKEN_FILE = os.getenv("DIGEST_GMAIL_TOKEN", "token.json")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Ollama settings
OLLAMA_BASE_URL = os.getenv("DIGEST_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("DIGEST_OLLAMA_MODEL", "llama3.1")

# TTS settings
TTS_VOICE = os.getenv("DIGEST_TTS_VOICE", "af_heart")
TTS_SPEED = float(os.getenv("DIGEST_TTS_SPEED", "1.0"))
TTS_LANG = os.getenv("DIGEST_TTS_LANG", "a")  # 'a' = American English

# Output settings
OUTPUT_DIR = Path(os.getenv("DIGEST_OUTPUT_DIR", "output"))
LINK_SKIP_RULES_FILE = Path(
    os.getenv("DIGEST_LINK_SKIP_RULES_FILE", "link_skip_rules.json")
)

# Email processing mode settings
def _split_regex_env(name):
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(";") if item.strip()]


FORCE_CONTENT_SUBJECT_REGEX = _split_regex_env("DIGEST_FORCE_CONTENT_SUBJECT_REGEX")
FORCE_CONTENT_SENDER_REGEX = _split_regex_env("DIGEST_FORCE_CONTENT_SENDER_REGEX")
FORCE_LINKS_SUBJECT_REGEX = _split_regex_env("DIGEST_FORCE_LINKS_SUBJECT_REGEX")
FORCE_LINKS_SENDER_REGEX = _split_regex_env("DIGEST_FORCE_LINKS_SENDER_REGEX")
EMAIL_CONTENT_MIN_WORDS = int(os.getenv("DIGEST_EMAIL_CONTENT_MIN_WORDS", "120"))
EMAIL_CONTENT_MAX_LINK_DENSITY = float(
    os.getenv("DIGEST_EMAIL_CONTENT_MAX_LINK_DENSITY", "0.15")
)
EMAIL_STORY_MIN_WORDS = int(os.getenv("DIGEST_EMAIL_STORY_MIN_WORDS", "80"))
EMAIL_STORY_MAX_WORDS = int(os.getenv("DIGEST_EMAIL_STORY_MAX_WORDS", "900"))

# Article fetch settings
FETCH_TIMEOUT = int(os.getenv("DIGEST_FETCH_TIMEOUT", "30"))

# Articles longer than this (in words) get a 3-minute summary instead of full text
ARTICLE_WORD_LIMIT = int(os.getenv("DIGEST_ARTICLE_WORD_LIMIT", "400"))

# SSL CA bundle (auto-detect Netskope or other corporate proxies)
_NETSKOPE_CERT = "/Library/Application Support/Netskope/STAgent/download/nscacert_combined.pem"
_default_ca = _NETSKOPE_CERT if os.path.exists(_NETSKOPE_CERT) else None
SSL_CA_FILE = os.getenv("DIGEST_SSL_CA_FILE", _default_ca)
