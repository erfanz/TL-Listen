#!/usr/bin/env python3
"""
Morning Digest Podcast Maker

Fetches digest emails from Gmail, extracts article links, fetches and
summarizes articles, and produces MP3 audio files for each one.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import config

# Propagate custom CA bundle to all libraries that use requests/urllib3
if config.SSL_CA_FILE:
    os.environ.setdefault("REQUESTS_CA_BUNDLE", config.SSL_CA_FILE)
    os.environ.setdefault("SSL_CERT_FILE", config.SSL_CA_FILE)
    os.environ.setdefault("CURL_CA_BUNDLE", config.SSL_CA_FILE)

from fetch_emails import fetch_digest_emails
from extract_links import extract_links
from fetch_articles import fetch_article
from summarize import summarize, summarize_extended
from text_to_speech import generate_article_audio


def _sanitize_filename(text, max_len=60):
    """Create a filesystem-safe filename from text."""
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return safe.strip().replace(" ", "_")[:max_len] or "article"


def run(dry_run=False):
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = config.OUTPUT_DIR / today
    text_dir = out_dir / "texts"
    mp3_dir = out_dir / "mp3"
    text_dir.mkdir(parents=True, exist_ok=True)
    mp3_dir.mkdir(parents=True, exist_ok=True)

    print(f"🌅 Morning Digest — {today}")
    print(f"   Output directory: {out_dir}\n")

    # 1. Fetch emails
    emails = fetch_digest_emails(mark_read=not dry_run)
    if not emails:
        print("Nothing to process. Exiting.")
        return

    # 2. Extract links from all emails
    all_articles = []
    for email in emails:
        urls = extract_links(email)
        print(f"  📧 \"{email['subject']}\" → {len(urls)} link(s)")
        for url in urls:
            all_articles.append({"url": url, "email_subject": email["subject"]})

    if not all_articles:
        print("\nNo article links found in digest emails. Exiting.")
        return

    print(f"\n🔗 Found {len(all_articles)} article(s) total. Processing...\n")

    # 3. Fetch, summarize, and generate audio for each article
    success_count = 0
    for i, item in enumerate(all_articles, 1):
        url = item["url"]
        print(f"[{i}/{len(all_articles)}] {url}")

        # Fetch article
        article = fetch_article(url)
        if not article:
            continue

        print(f"  📄 \"{article['title']}\" ({len(article['text'])} chars)")

        # Summarize
        print("  🤖 Summarizing...")
        summary = summarize(article["text"], title=article["title"])
        print(f"  📝 Summary: {summary[:100]}...")

        # Check if article is too long — use extended summary instead of full text
        word_count = len(article["text"].split())
        is_long = word_count > config.ARTICLE_WORD_LIMIT
        if is_long:
            print(f"  📏 Article is {word_count} words (>{config.ARTICLE_WORD_LIMIT}) — generating extended summary...")
            extended_summary = summarize_extended(article["text"], title=article["title"])
            body_text = extended_summary
        else:
            body_text = article["text"]

        # Save text (summary + article or extended summary)
        filename = f"{i:03d}_{_sanitize_filename(article['title'])}"
        text_file = text_dir / f"{filename}.txt"
        if is_long:
            text_file.write_text(
                f"Title: {article['title']}\n"
                f"URL: {article['url']}\n\n"
                f"--- Summary ---\n{summary}\n\n"
                f"--- Extended Summary (article was {word_count} words) ---\n{body_text}\n",
                encoding="utf-8",
            )
        else:
            text_file.write_text(
                f"Title: {article['title']}\n"
                f"URL: {article['url']}\n\n"
                f"--- Summary ---\n{summary}\n\n"
                f"--- Full Article ---\n{article['text']}\n",
                encoding="utf-8",
            )
        print(f"  💾 {text_file}")

        if dry_run:
            print("  ⏭️  Dry run — skipping audio generation.\n")
            continue

        # Generate audio
        output_path = mp3_dir / filename
        print("  🎙️  Generating audio...")
        result_file = generate_article_audio(
            article["title"], summary, body_text, output_path,
            is_long=is_long,
        )
        print(f"  ✅ {result_file}\n")
        success_count += 1

    print(f"\n🎉 Done! Generated {success_count} audio file(s) in {mp3_dir}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("🔍 DRY RUN MODE — no emails will be marked as read, no audio generated.\n")
    run(dry_run=dry)
