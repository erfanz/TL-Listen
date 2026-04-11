#!/usr/bin/env python3
"""
Morning Digest Podcast Maker

Fetches digest emails from Gmail, extracts article links, fetches and
summarizes articles, and produces MP3 audio files for each one.
"""

import os
import sys
from collections import OrderedDict

import config
import re

# Propagate custom CA bundle to all libraries that use requests/urllib3
if config.SSL_CA_FILE:
    os.environ.setdefault("REQUESTS_CA_BUNDLE", config.SSL_CA_FILE)
    os.environ.setdefault("SSL_CERT_FILE", config.SSL_CA_FILE)
    os.environ.setdefault("CURL_CA_BUNDLE", config.SSL_CA_FILE)

from fetch_emails import fetch_digest_emails
from extract_links import extract_links_with_details, get_specialized_link_parser_name
from fetch_articles import resolve_article_url
from email_processing import _decide_email_mode, _plain_email_content
from parsers import get_specialized_parser_name
from summarize import split_email_stories
from shared.pipeline import create_dated_output_dirs, process_article_queue
from shared.reporting import sanitize_filename, write_summary_report

def extract_sender_name(sender):
    # Extracts the display name from 'Name <email@domain>' or returns as-is if no angle brackets
    match = re.match(r'\s*"?([^"<]*)"?\s*<.*?>', sender)
    if match:
        return match.group(1).strip() or sender.strip()
    return sender.strip()

def _write_summary_report(email_results, out_dir):
    write_summary_report(
        email_results,
        out_dir,
        heading_title="EMAIL DIGEST — PROCESSING SUMMARY",
        group_icon="📧",
        metadata_label="Parser",
        metadata_key="parser_name",
        metadata_default="default",
        group_json_key="email_subject",
    )


def run(dry_run=False):
    today, out_dir, created_dirs = create_dated_output_dirs(
        config.OUTPUT_DIR,
        "texts",
        "mp3",
        "raw_emails",
    )
    text_dir = created_dirs["texts"]
    mp3_dir = created_dirs["mp3"]
    raw_emails_dir = created_dirs["raw_emails"]

    print(f"🌅 Morning Digest — {today}")
    print(f"   Output directory: {out_dir}\n")

    # 1. Fetch emails
    emails = fetch_digest_emails(mark_read=not dry_run)
    if not emails:
        print("Nothing to process. Exiting.")
        return

    # Save raw emails for debugging
    for idx, email in enumerate(emails, 1):
        safe_subj = sanitize_filename(email["subject"])
        email_file = raw_emails_dir / f"{idx:03d}_{safe_subj}.txt"
        email_file.write_text(
            f"Subject: {email['subject']}\n"
            f"From: {extract_sender_name(email['from'])}\n"
            f"Date: {email.get('date', '')}\n"
            f"Gmail ID: {email['id']}\n"
            f"{'=' * 60}\n\n"
            f"--- Plain Text ---\n{email['text']}\n\n"
            f"--- HTML ---\n{email['html']}\n",
            encoding="utf-8",
        )
    print(f"   Raw emails saved to {raw_emails_dir}\n")

    # 2. Decide per-email mode and build work queue
    all_articles = []
    content_story_count = 0
    queued_resolved_urls = set()
    email_results = OrderedDict()  # email_subject -> {parser_name, articles}
    for email in emails:
        mode, mode_reason, link_details = _decide_email_mode(email)
        parser_name = get_specialized_parser_name(email) or get_specialized_link_parser_name(email)
        if email["subject"] not in email_results:
            email_results[email["subject"]] = {
                "parser_name": parser_name,
                "articles": [],
            }
        elif parser_name and not email_results[email["subject"]].get("parser_name"):
            email_results[email["subject"]]["parser_name"] = parser_name

        print(f"  📧 \"{email['subject']}\" → mode={mode} ({mode_reason})")
        if mode == "content":
            content = _plain_email_content(email)
            if not content:
                print("     ⚠️  Empty email body. Skipping.")
                continue
            stories = split_email_stories(email, email_subject=email["subject"])
            content_story_count += len(stories)
            print(f"     {len(stories)} story chunk(s) found in email body. Internal links ignored.")
            for story_idx, story in enumerate(stories, 1):
                all_articles.append({
                    "url": f"gmail://message/{email['id']}#story-{story_idx}",
                    "resolved_url": f"gmail://message/{email['id']}#story-{story_idx}",
                    "email_subject": email["subject"],
                    "source_type": "email_story",
                    "title_hint": story.get("title") or f"{email['subject']} — Story {story_idx}",
                    "text_override": story["text"],
                    "source_name": email["from"],
                    "date": email.get("date", ""),
                })
            continue

        if link_details is None:
            link_details = extract_links_with_details(email)
        urls = link_details["article_urls"]
        skipped = link_details["skipped_urls"]
        new_items = []
        for url in urls:
            resolved_url = resolve_article_url(url)
            if resolved_url in queued_resolved_urls:
                continue
            queued_resolved_urls.add(resolved_url)
            new_items.append({"url": url, "resolved_url": resolved_url})

        print(
            f"     {link_details['raw_count']} raw link(s), "
            f"{len(skipped)} skipped by filters, {len(urls)} candidate article link(s), "
            f"{len(new_items)} unique to fetch (after redirect resolution)"
        )
        if skipped:
            print("     Links skipped by filters:")
            for idx, item in enumerate(skipped, 1):
                print(f"       {idx}. [{item['reason']}] {item['url']}")
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
                "source_type": "external_url",
                "source_name": email["from"],
                "date": email.get("date", ""),
            })

    if not all_articles:
        print("\nNo processable content found in digest emails. Exiting.")
        return

    if content_story_count:
        print(f"\n🔗 Found {len(all_articles)} item(s) total ({content_story_count} from email stories). Processing...\n")
    else:
        print(f"\n🔗 Found {len(all_articles)} item(s) total. Processing...\n")

    # 3. Fetch, summarize, and generate audio for each article
    success_count = process_article_queue(
        all_articles,
        text_dir=text_dir,
        mp3_dir=mp3_dir,
        dry_run=dry_run,
        group_results=email_results,
        group_key_field="email_subject",
    )

    # 4. Write per-email summary report
    _write_summary_report(email_results, out_dir)

    print(f"\n🎉 Done! Generated {success_count} audio file(s) in {mp3_dir}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("🔍 DRY RUN MODE — no emails will be marked as read, no audio generated.\n")
    run(dry_run=dry)
