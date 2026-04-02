#!/usr/bin/env python3
"""
Morning Digest Podcast Maker

Fetches digest emails from Gmail, extracts article links, fetches and
summarizes articles, and produces MP3 audio files for each one.
"""

import json
import os
import sys
from collections import OrderedDict
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
from fetch_articles import fetch_article, resolve_article_url
from summarize import summarize, summarize_extended
from text_to_speech import generate_article_audio


def _sanitize_filename(text, max_len=60):
    """Create a filesystem-safe filename from text."""
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return safe.strip().replace(" ", "_")[:max_len] or "article"


def _write_summary_report(email_results, out_dir):
    """Write a per-email summary report (text table + JSON) to the output dir."""
    report_path = out_dir / "summary.txt"
    json_path = out_dir / "summary.json"

    lines = ["=" * 80, "  EMAIL DIGEST — PROCESSING SUMMARY", "=" * 80, ""]

    json_data = []
    for email_subject, articles in email_results.items():
        lines.append(f"📧 {email_subject}")
        lines.append("-" * 80)
        lines.append(f"  {'#':<4} {'Article Title':<40} {'Audio':>6}  URL")
        lines.append(f"  {'—'*3:<4} {'—'*38:<40} {'—'*5:>6}  {'—'*40}")

        email_json = {"email_subject": email_subject, "articles": []}
        for idx, art in enumerate(articles, 1):
            title_display = (art["title"] or "⚠️ Failed to fetch")[:38]
            audio_flag = "  ✅" if art["audio"] else "  ❌"
            lines.append(f"  {idx:<4} {title_display:<40} {audio_flag:>6}  {art['url']}")
            email_json["articles"].append({
                "url": art["url"],
                "title": art["title"],
                "audio_produced": art["audio"],
            })

        total = len(articles)
        audio_count = sum(1 for a in articles if a["audio"])
        fetched_count = sum(1 for a in articles if a["title"])
        lines.append("")
        lines.append(f"  Total: {total} URL(s) | {fetched_count} fetched | {audio_count} audio file(s)")
        lines.append("")
        json_data.append(email_json)

    report_text = "\n".join(lines) + "\n"
    report_path.write_text(report_text, encoding="utf-8")
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\n📊 Summary report saved to {report_path}")
    print(f"   JSON data saved to {json_path}")
    print()
    print(report_text)


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

    # 2. Extract links from all emails and dedupe by resolved destination
    all_articles = []
    queued_resolved_urls = set()
    email_results = OrderedDict()  # email_subject -> list of result dicts
    for email in emails:
        urls = extract_links(email)
        new_items = []
        for url in urls:
            resolved_url = resolve_article_url(url)
            if resolved_url in queued_resolved_urls:
                continue
            queued_resolved_urls.add(resolved_url)
            new_items.append({"url": url, "resolved_url": resolved_url})

        print(
            f"  📧 \"{email['subject']}\" → {len(urls)} link(s) found, "
            f"{len(new_items)} unique to fetch (after redirect resolution)"
        )
        if email["subject"] not in email_results:
            email_results[email["subject"]] = []
        if new_items:
            print("     Links queued for fetch:")
            for idx, item in enumerate(new_items, 1):
                url = item["url"]
                resolved_url = item["resolved_url"]
                if resolved_url != url:
                    print(f"       {idx}. {url} -> {resolved_url}")
                else:
                    print(f"       {idx}. {url}")
        else:
            print("     No new links to fetch (all duplicates).")

        for item in new_items:
            all_articles.append({
                "url": item["url"],
                "resolved_url": item["resolved_url"],
                "email_subject": email["subject"],
            })

    if not all_articles:
        print("\nNo article links found in digest emails. Exiting.")
        return

    print(f"\n🔗 Found {len(all_articles)} article(s) total. Processing...\n")

    # 3. Fetch, summarize, and generate audio for each article
    success_count = 0
    for i, item in enumerate(all_articles, 1):
        url = item["url"]
        resolved_url = item["resolved_url"]
        email_subj = item["email_subject"]
        print(f"[{i}/{len(all_articles)}] {url}")

        # Fetch article
        article = fetch_article(url, resolved_url=resolved_url)
        if not article:
            email_results[email_subj].append({
                "url": url,
                "title": None,
                "audio": False,
            })
            continue

        title = article["title"]
        print(f"  📄 \"{title}\" ({len(article['text'])} chars)")

        # Summarize
        print("  🤖 Summarizing...")
        summary = summarize(article["text"], title=title)
        print(f"  📝 Summary: {summary[:100]}...")

        # Check if article is too long — use extended summary instead of full text
        word_count = len(article["text"].split())
        is_long = word_count > config.ARTICLE_WORD_LIMIT
        if is_long:
            print(f"  📏 Article is {word_count} words (>{config.ARTICLE_WORD_LIMIT}) — generating extended summary...")
            extended_summary = summarize_extended(article["text"], title=title)
            body_text = extended_summary
        else:
            body_text = article["text"]

        # Save text (summary + article or extended summary)
        filename = f"{i:03d}_{_sanitize_filename(title)}"
        text_file = text_dir / f"{filename}.txt"
        if is_long:
            text_file.write_text(
                f"Title: {title}\n"
                f"URL: {article['url']}\n\n"
                f"--- Summary ---\n{summary}\n\n"
                f"--- Extended Summary (article was {word_count} words) ---\n{body_text}\n",
                encoding="utf-8",
            )
        else:
            text_file.write_text(
                f"Title: {title}\n"
                f"URL: {article['url']}\n\n"
                f"--- Summary ---\n{summary}\n\n"
                f"--- Full Article ---\n{article['text']}\n",
                encoding="utf-8",
            )
        print(f"  💾 {text_file}")

        if dry_run:
            print("  ⏭️  Dry run — skipping audio generation.\n")
            email_results[email_subj].append({
                "url": url,
                "title": title,
                "audio": False,
            })
            continue

        # Generate audio
        output_path = mp3_dir / filename
        print("  🎙️  Generating audio...")
        audio_ok = False
        try:
            result_file = generate_article_audio(
                title, summary, body_text, output_path,
                is_long=is_long,
            )
            print(f"  ✅ {result_file}\n")
            audio_ok = True
            success_count += 1
        except Exception as exc:
            print(f"  ❌ Audio generation failed: {exc}\n")

        email_results[email_subj].append({
            "url": url,
            "title": title,
            "audio": audio_ok,
        })

    # 4. Write per-email summary report
    _write_summary_report(email_results, out_dir)

    print(f"\n🎉 Done! Generated {success_count} audio file(s) in {mp3_dir}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("🔍 DRY RUN MODE — no emails will be marked as read, no audio generated.\n")
    run(dry_run=dry)
