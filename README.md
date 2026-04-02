# 🌅 Morning Digest Podcast Maker

Turn your daily email digests into a podcast you can listen to on your commute.

This tool automatically fetches digest emails from Gmail, extracts article links,
summarizes each article using a local LLM (Ollama), and produces MP3 audio files
using Kokoro TTS.

## Architecture

| Module | Purpose |
|---|---|
| `config.py` | Settings (Gmail label, Ollama model, output dir) |
| `fetch_emails.py` | Gmail API OAuth2 → fetch unread `digests` emails |
| `extract_links.py` | Parse email HTML → extract article URLs |
| `fetch_articles.py` | Fetch URLs → extract article text (trafilatura) |
| `summarize.py` | Ollama local LLM → concise summary |
| `text_to_speech.py` | Kokoro TTS → WAV → MP3 (via ffmpeg) |
| `main.py` | Orchestrator wiring it all together |

## Prerequisites

- **Python 3.10+**
- **ffmpeg** — for WAV→MP3 conversion (`brew install ffmpeg`)
- **Ollama** — running locally with a model pulled
  ```bash
  brew install ollama
  ollama pull llama3.1
  ollama serve
  ```
- **Google Cloud OAuth2 credentials** — for Gmail API access (see setup below)

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Gmail API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Application type: **Desktop app**
6. Download the JSON and save it as `credentials.json` in this directory
7. On first run, a browser window will open for you to authorize access
8. The token is cached in `token.json` for subsequent runs

### 3. Gmail label

Create a label called `digests` in Gmail and apply it to your digest/newsletter emails.
You can change the label name via the `DIGEST_GMAIL_LABEL` environment variable.

## Usage

```bash
# Full run — fetches emails, processes articles, generates MP3s
python main.py

# Dry run — fetches articles and saves full text, but skips summarization, audio generation, & email marking
python main.py --dry-run
```

Output files are saved to `output/YYYY-MM-DD/` with one MP3 per article.

Each MP3 follows this format:
1. Article title announcement
2. Summary (3-5 sentences)
3. Full article text, or a long summary of it if it's too long.

## Configuration

All settings can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `DIGEST_GMAIL_LABEL` | `digests` | Gmail label to filter |
| `DIGEST_GMAIL_CREDENTIALS` | `credentials.json` | Path to OAuth credentials |
| `DIGEST_GMAIL_TOKEN` | `token.json` | Path to cached auth token |
| `DIGEST_OLLAMA_URL` | `http://localhost:11434` | Ollama API base URL |
| `DIGEST_OLLAMA_MODEL` | `llama3.1` | Ollama model for summarization |
| `DIGEST_TTS_VOICE` | `af_heart` | Kokoro voice name |
| `DIGEST_TTS_SPEED` | `1.0` | TTS playback speed |
| `DIGEST_OUTPUT_DIR` | `output` | Output directory for MP3 files |
| `DIGEST_LINK_SKIP_RULES_FILE` | `link_skip_rules.json` | JSON file with URL skip rules for link extraction |
| `DIGEST_SSL_CA_FILE` | *(auto-detect)* | Custom CA bundle for corporate proxies |

### Configurable link skip rules

`extract_links.py` loads URL skip rules from `link_skip_rules.json` (or the file path set in
`DIGEST_LINK_SKIP_RULES_FILE`).

The file is a JSON array of rule objects. Each rule can include:
- `domain` (optional): exact host match (e.g., `news.ycombinator.com`)
- `path_regex` (optional): regex against URL path
- `query_regex` (optional): regex against URL query string

If a URL matches a rule, it is skipped during extraction.

Example:
```json
[
  { "domain": "news.ycombinator.com", "path_regex": "^/item$" },
  { "domain": "hndigest.com", "path_regex": "^/m/[^/]+/c/\\d+$" }
]
```

### Corporate proxy / SSL

If you're behind a corporate proxy (e.g. Netskope, Zscaler), the tool auto-detects
the Netskope CA bundle. For other proxies, set the `DIGEST_SSL_CA_FILE` env variable
to your corporate CA bundle path.

## Automating (cron)

To run every morning at 7 AM:

```bash
crontab -e
```

```
0 7 * * * cd /path/to/morning_digest_podcast_maker && .venv/bin/python main.py >> cron.log 2>&1
```
