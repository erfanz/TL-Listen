#!/usr/bin/env python3
"""
RSS Digest Podcast Maker

Fetches RSS/Atom feeds, processes newly published articles since the last
checkpoint, summarizes them, and produces MP3 audio files.
"""

import os
import sys
from collections import OrderedDict

import config
from fetch_articles import resolve_article_url
from fetch_feeds import (
    fetch_feed_entries,
    get_feed_checkpoint,
    load_feed_state,
    save_feed_state,
    set_feed_checkpoint,
)
from shared.pipeline import create_dated_output_dirs, process_article_queue
from shared.reporting import write_summary_report

# Propagate custom CA bundle to all libraries that use requests/urllib3
if config.SSL_CA_FILE:
    os.environ.setdefault("REQUESTS_CA_BUNDLE", config.SSL_CA_FILE)
    os.environ.setdefault("SSL_CERT_FILE", config.SSL_CA_FILE)
    os.environ.setdefault("CURL_CA_BUNDLE", config.SSL_CA_FILE)


def _write_summary_report(feed_results, out_dir):
    write_summary_report(
        feed_results,
        out_dir,
        heading_title="RSS DIGEST — PROCESSING SUMMARY",
        group_icon="📰",
        metadata_label="Feed URL",
        metadata_key="feed_url",
        metadata_default="(unknown)",
        group_json_key="feed_title",
    )


def run(dry_run=False):
    if not config.RSS_FEED_URLS:
        raise ValueError(
            "No RSS feeds configured. Add one or more feed URLs under rss.feed_urls in config.json."
        )

    today, out_dir, created_dirs = create_dated_output_dirs(
        config.RSS_OUTPUT_DIR,
        "texts",
        "mp3",
    )
    text_dir = created_dirs["texts"]
    mp3_dir = created_dirs["mp3"]

    print(f"📰 RSS Digest — {today}")
    print(f"   Output directory: {out_dir}")
    print(f"   State file: {config.RSS_STATE_FILE}\n")

    state = load_feed_state()
    all_articles = []
    feed_results = OrderedDict()
    queued_resolved_urls = set()
    latest_checkpoints = {}

    for feed_url in config.RSS_FEED_URLS:
        checkpoint = get_feed_checkpoint(state, feed_url)
        feed_data = fetch_feed_entries(feed_url, checkpoint=checkpoint)
        feed_key = feed_url
        feed_results[feed_key] = {
            "display_name": feed_data["feed_title"],
            "feed_url": feed_url,
            "articles": [],
        }

        checkpoint_display = feed_data["effective_checkpoint"].isoformat()
        print(
            f"  📰 \"{feed_data['feed_title']}\" → {len(feed_data['entries'])} new item(s) since {checkpoint_display}"
        )

        if feed_data["entries"]:
            latest_checkpoints[feed_url] = max(
                entry["published_at"] for entry in feed_data["entries"]
            )

        for entry in feed_data["entries"]:
            resolved_url = resolve_article_url(entry["url"])
            if resolved_url in queued_resolved_urls:
                print(f"     ⏭️  Duplicate article skipped: {entry['url']}")
                continue
            queued_resolved_urls.add(resolved_url)
            all_articles.append(
                {
                    "url": entry["url"],
                    "resolved_url": resolved_url,
                    "feed_key": feed_key,
                    "source_type": "external_url",
                    "title_hint": entry["title"],
                }
            )

    if not all_articles:
        print("\nNo new RSS items to process. Exiting.")
        return

    print(f"\n🔗 Found {len(all_articles)} item(s) total. Processing...\n")
    success_count = process_article_queue(
        all_articles,
        text_dir=text_dir,
        mp3_dir=mp3_dir,
        dry_run=dry_run,
        group_results=feed_results,
        group_key_field="feed_key",
    )

    _write_summary_report(feed_results, out_dir)

    if dry_run:
        print("\n🔍 Dry run — checkpoint file not updated.")
    else:
        for feed_url, checkpoint in latest_checkpoints.items():
            set_feed_checkpoint(state, feed_url, checkpoint)
        save_feed_state(state)
        print(f"\n💾 RSS checkpoints saved to {config.RSS_STATE_FILE}")

    print(f"\n🎉 Done! Generated {success_count} audio file(s) in {mp3_dir}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("🔍 DRY RUN MODE — no checkpoint will be updated, no audio generated.\n")
    run(dry_run=dry)
