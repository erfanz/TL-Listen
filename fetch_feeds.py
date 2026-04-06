import json
from calendar import timegm
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

import config
from shared.text_cleaning import normalize_title

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _to_utc_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def parse_entry_timestamp(entry):
    """Extract a timezone-aware UTC timestamp from an RSS/Atom entry."""
    for field_name in ("published_parsed", "updated_parsed"):
        parsed_value = entry.get(field_name)
        if parsed_value:
            return datetime.fromtimestamp(timegm(parsed_value), tz=timezone.utc)

    for field_name in ("published", "updated"):
        raw_value = entry.get(field_name)
        if not raw_value:
            continue
        parsed_value = parsedate_to_datetime(raw_value)
        return parsed_value.astimezone(timezone.utc) if parsed_value.tzinfo else parsed_value.replace(tzinfo=timezone.utc)

    return None


def filter_feed_entries(entries, checkpoint=None, now=None, initial_window_days=None):
    """Keep feed entries newer than the checkpoint, or the initial window on first run."""
    current_time = _to_utc_datetime(now) or datetime.now(timezone.utc)
    window_days = initial_window_days or config.RSS_INITIAL_WINDOW_DAYS
    effective_checkpoint = _to_utc_datetime(checkpoint) or (current_time - timedelta(days=window_days))

    filtered_entries = []
    for entry in entries:
        published_at = parse_entry_timestamp(entry)
        if published_at is None or published_at <= effective_checkpoint:
            continue

        url = str(entry.get("link") or "").strip()
        if not url:
            continue

        filtered_entries.append(
            {
                "title": normalize_title(entry.get("title") or "") or "Untitled",
                "url": url,
                "published_at": published_at,
            }
        )

    filtered_entries.sort(key=lambda item: (item["published_at"], item["url"]))
    return filtered_entries, effective_checkpoint


def load_feed_state(path=None):
    """Load persisted RSS checkpoints."""
    state_path = path or config.RSS_STATE_FILE
    if not state_path.exists():
        return {"feeds": {}}

    data = json.loads(state_path.read_text(encoding="utf-8"))
    feeds = data.get("feeds")
    if not isinstance(feeds, dict):
        raise ValueError(f"{state_path} must contain a JSON object with a 'feeds' object")
    return data


def save_feed_state(state, path=None):
    """Persist RSS checkpoints."""
    state_path = path or config.RSS_STATE_FILE
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_feed_checkpoint(state, feed_url):
    """Return the saved checkpoint for a feed URL, if any."""
    raw_value = state.get("feeds", {}).get(feed_url, {}).get("last_published")
    if not raw_value:
        return None
    parsed_value = datetime.fromisoformat(raw_value)
    return parsed_value.astimezone(timezone.utc) if parsed_value.tzinfo else parsed_value.replace(tzinfo=timezone.utc)


def set_feed_checkpoint(state, feed_url, checkpoint):
    """Update the saved checkpoint for a feed URL."""
    if checkpoint is None:
        return
    state.setdefault("feeds", {})
    state["feeds"].setdefault(feed_url, {})
    state["feeds"][feed_url]["last_published"] = checkpoint.astimezone(timezone.utc).isoformat()


def fetch_feed_entries(feed_url, checkpoint=None, now=None):
    """Fetch and filter feed entries for one RSS/Atom feed."""
    response = requests.get(
        feed_url,
        timeout=config.RSS_FETCH_TIMEOUT,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        },
    )
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Invalid feed returned from {feed_url}: {parsed.bozo_exception}")

    entries, effective_checkpoint = filter_feed_entries(
        parsed.entries,
        checkpoint=checkpoint,
        now=now,
        initial_window_days=config.RSS_INITIAL_WINDOW_DAYS,
    )
    return {
        "feed_title": normalize_title(parsed.feed.get("title") or feed_url) or feed_url,
        "feed_url": feed_url,
        "effective_checkpoint": effective_checkpoint,
        "entries": entries,
    }
