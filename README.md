# 🌅 TL-Listen

Turn either email digests or RSS feeds into a podcast you can listen to on your commute.

This repository now contains two entry points that share the same article-processing pipeline:
1. **Email app (`main.py`)**: fetch unread Gmail digests, extract stories, summarize them, and generate audio.
2. **RSS app (`rss_main.py`)**: fetch RSS/Atom feeds, keep a checkpoint per feed, summarize newly published entries, and generate audio.

## Architecture

| Module | Purpose |
|---|---|
| `config.json` | Single source of truth for app configuration |
| `config.py` | JSON config loader + normalized settings |
| `fetch_emails.py` | Gmail API OAuth2 → fetch unread `digests` emails |
| `fetch_feeds.py` | RSS/Atom fetch + checkpoint filtering |
| `extract_links.py` | Parse email HTML → extract article URLs |
| `fetch_articles.py` | Fetch URLs → extract article text (trafilatura) |
| `summarize.py` | Ollama local LLM → concise summary |
| `text_to_speech.py` | Kokoro TTS → WAV → MP3 (via ffmpeg) |
| `shared/pipeline.py` | Shared fetch/summarize/text/audio orchestration |
| `shared/reporting.py` | Shared summary report generation |
| `main.py` | Email app entry point |
| `rss_main.py` | RSS app entry point |

## Prerequisites

- **Python 3.12** — recommended because Kokoro is installed for Python 3.12 in this project
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

### 2. Edit `config.json`

All runtime configuration now lives in `config.json`.

Example:
```json
{
  "gmail": {
    "label": "digests",
    "credentials_file": "credentials.json",
    "token_file": "token.json"
  },
  "rss": {
    "feed_urls": [
      "https://example.com/feed.xml"
    ]
  }
}
```

### 3. Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Gmail API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Application type: **Desktop app**
6. Download the JSON and save it as `credentials.json` in this directory
7. On first run, a browser window will open for you to authorize access
8. The token is cached in `token.json` for subsequent runs

### 4. Gmail label

Create a label called `digests` in Gmail and apply it to your digest/newsletter emails.
You can change the label in `config.json` under `gmail.label`.

## Usage

```bash
# Email app: full run
python3.12 main.py

# Email app: dry run
python3.12 main.py --dry-run

# RSS app: full run
python3.12 rss_main.py

# RSS app: dry run
python3.12 rss_main.py --dry-run
```

Email output is saved to `output/YYYY-MM-DD/`.
RSS output is saved to `output/rss/YYYY-MM-DD/` by default.

Each MP3 follows this format:
1. Article title announcement
2. Summary (3-5 sentences)
3. Full article text, or a long summary of it if it's too long.

## Configuration

All settings live in `config.json`.

### Top-level sections

| Section | Purpose |
|---|---|
| `gmail` | Gmail label, credentials path, token path, scopes |
| `ollama` | Local LLM endpoint + model |
| `tts` | Kokoro voice, speed, and language |
| `output` | Shared output directory and link skip rules file |
| `email_processing` | Email classification thresholds, regex rules, specialized parser rules |
| `article_fetch` | HTTP timeout and long-article word limit |
| `ssl` | Optional custom CA bundle path |
| `rss` | Feed URLs, checkpoint file, RSS output dir, RSS fetch timeout, first-run window |

### `config.json` reference

| JSON path | Default | Description |
|---|---|---|
| `gmail.label` | `digests` | Gmail label to filter |
| `gmail.credentials_file` | `credentials.json` | Path to OAuth credentials |
| `gmail.token_file` | `token.json` | Path to cached auth token |
| `gmail.scopes` | Gmail modify scope | OAuth scopes for Gmail access |
| `ollama.base_url` | `http://localhost:11434` | Ollama API base URL |
| `ollama.model` | `llama3.1` | Ollama model for summarization |
| `tts.voice` | `af_heart` | Kokoro voice name |
| `tts.speed` | `1.0` | TTS playback speed |
| `tts.lang` | `a` | Kokoro language code |
| `output.dir` | `output` | Base output directory |
| `output.link_skip_rules_file` | `link_skip_rules.json` | JSON file with URL skip rules for link extraction |
| `email_processing.content_min_words` | `120` | Min email body words to consider content mode |
| `email_processing.content_max_link_density` | `0.03` | Max links/word ratio for content mode |
| `email_processing.story_min_words` | `80` | Minimum words per story chunk in content emails |
| `email_processing.story_max_words` | `900` | Preferred max story chunk size |
| `email_processing.force_content_subject_regex` | `[]` | Regex strings to force content mode by subject |
| `email_processing.force_content_sender_regex` | `["snacks.robinhood.com"]` | Regex strings to force content mode by sender |
| `email_processing.force_links_subject_regex` | `[]` | Regex strings to force links mode by subject |
| `email_processing.force_links_sender_regex` | `["hndigest.com"]` | Regex strings to force links mode by sender |
| `email_processing.content_parser_sender_rules` | `[{ "pattern": "snacks\\.robinhood\\.com", "parser": "robinhood" }]` | Array of `{ "pattern", "parser" }` rules for content parsers |
| `email_processing.link_parser_sender_rules` | `[{ "pattern": "hndigest\\.com", "parser": "hackernews_digest" }]` | Array of `{ "pattern", "parser" }` rules for link parsers |
| `article_fetch.timeout` | `30` | HTTP timeout for article fetches |
| `article_fetch.word_limit` | `400` | Long-article threshold for extended summaries |
| `summarization.summary_sentence_count` | `4` | Target sentence count for the normal summary |
| `summarization.summary_max_tokens` | `300` | Ollama token cap for the normal summary |
| `summarization.extended_summary_word_count` | `450` | Target word count for the extended summary |
| `summarization.extended_summary_max_tokens` | `800` | Ollama token cap for the extended summary |
| `ssl.ca_file` | `null` | Optional CA bundle path; if null, Netskope auto-detection still applies |
| `rss.feed_urls` | `[]` | RSS/Atom feed URLs |
| `rss.state_file` | `rss_state.json` | JSON checkpoint file storing latest processed publish time per feed |
| `rss.output_dir` | `output/rss` | Output directory for RSS text and audio files |
| `rss.fetch_timeout` | `30` | Timeout for fetching feed XML |
| `rss.initial_window_days` | `7` | On first run with no checkpoint, process only entries from the last N days |

On the first RSS run, the app does **not** process the full history of a feed. It only processes entries published within the last 7 days by default, then persists a checkpoint for later runs.

### Email mode routing (links vs content)

Each email is automatically classified:
- **links mode**: behaves like before (extract URLs, fetch external articles)
- **content mode**: ignores internal links and processes the email body itself

Content-mode emails are split into multiple story chunks using the local LLM, so one email can
produce multiple audio items. If splitting output is invalid, the app falls back to a single
story chunk for that email.

If auto-detection misclassifies a newsletter, edit the regex arrays in `config.json`, for example:
```json
"force_content_sender_regex": ["mynewsletter\\.com", "Substack"],
"force_links_subject_regex": ["Hacker News Digest", "Link Roundup"]
```

### Specialized link parsers

For newsletters whose HTML mixes article links with lots of navigation or tracking links, you can
route matching senders through a specialized link parser:

```json
"link_parser_sender_rules": [
  { "pattern": "hndigest\\.com", "parser": "hackernews_digest" }
]
```

The built-in `hackernews_digest` parser only keeps links that match the exact HTML shape
`tr > th > a` and ignores all other anchors in the email.

### Configurable link skip rules

`extract_links.py` loads URL skip rules from `link_skip_rules.json` by default, or from the path in
`output.link_skip_rules_file`.

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
the Netskope CA bundle. For other proxies, set `ssl.ca_file` in `config.json`
to your corporate CA bundle path.

## Automating (cron)

To run the email app every morning at 7 AM:

```bash
crontab -e
```

```
0 7 * * * cd /path/to/TL-Listen && .venv/bin/python3.12 main.py >> cron.log 2>&1
```

To poll RSS every 30 minutes:

```
*/30 * * * * cd /path/to/TL-Listen && .venv/bin/python3.12 rss_main.py >> rss-cron.log 2>&1
```
