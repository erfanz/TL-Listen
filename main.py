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
from extract_links import extract_links_with_details
from fetch_articles import fetch_article, resolve_article_url
from email_processing import _decide_email_mode, _plain_email_content
from parsers import get_specialized_parser_name
from summarize import summarize, summarize_extended, split_email_stories
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
    for email_subject, email_result in email_results.items():
        parser_name = email_result.get("parser_name") or "default"
        articles = email_result["articles"]
        lines.append(f"📧 {email_subject}")
        lines.append(f"   Parser: {parser_name}")
        lines.append("-" * 80)
        lines.append(f"  {'#':<4} {'Source':<12} {'Article Title':<28} {'Audio':>6}  URL")
        lines.append(f"  {'—'*3:<4} {'—'*10:<12} {'—'*26:<28} {'—'*5:>6}  {'—'*28}")

        email_json = {
            "email_subject": email_subject,
            "parser_name": parser_name,
            "articles": [],
        }
        for idx, art in enumerate(articles, 1):
            title_display = (art["title"] or "⚠️ Failed to fetch")[:26]
            source_display = (art.get("source_type") or "external_url")[:10]
            audio_flag = "  ✅" if art["audio"] else "  ❌"
            lines.append(
                f"  {idx:<4} {source_display:<12} {title_display:<28} {audio_flag:>6}  {art['url']}"
            )
            email_json["articles"].append({
                "url": art["url"],
                "title": art["title"],
                "audio_produced": art["audio"],
                "source_type": art.get("source_type", "external_url"),
            })

        total = len(articles)
        audio_count = sum(1 for a in articles if a["audio"])
        fetched_count = sum(1 for a in articles if a["title"])
        lines.append("")
        lines.append(f"  Total: {total} item(s) | {fetched_count} fetched | {audio_count} audio file(s)")
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
    raw_emails_dir = out_dir / "raw_emails"
    text_dir.mkdir(parents=True, exist_ok=True)
    mp3_dir.mkdir(parents=True, exist_ok=True)
    raw_emails_dir.mkdir(parents=True, exist_ok=True)

    print(f"🌅 Morning Digest — {today}")
    print(f"   Output directory: {out_dir}\n")

    # 1. Fetch emails
    emails = fetch_digest_emails(mark_read=not dry_run)
    if not emails:
        print("Nothing to process. Exiting.")
        return

    # Save raw emails for debugging
    for idx, email in enumerate(emails, 1):
        safe_subj = _sanitize_filename(email["subject"])
        email_file = raw_emails_dir / f"{idx:03d}_{safe_subj}.txt"
        email_file.write_text(
            f"Subject: {email['subject']}\n"
            f"From: {email['from']}\n"
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
        parser_name = get_specialized_parser_name(email)
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
            })

    if not all_articles:
        print("\nNo processable content found in digest emails. Exiting.")
        return

    if content_story_count:
        print(f"\n🔗 Found {len(all_articles)} item(s) total ({content_story_count} from email stories). Processing...\n")
    else:
        print(f"\n🔗 Found {len(all_articles)} item(s) total. Processing...\n")

    # 3. Fetch, summarize, and generate audio for each article
    success_count = 0
    for i, item in enumerate(all_articles, 1):
        url = item["url"]
        resolved_url = item["resolved_url"]
        email_subj = item["email_subject"]
        source_type = item.get("source_type", "external_url")
        print(f"[{i}/{len(all_articles)}] {url}")

        if source_type == "email_story":
            article = {
                "url": url,
                "original_url": url,
                "title": item.get("title_hint") or "Email story",
                "text": item["text_override"],
            }
            print("  📨 Using email story content (no external fetch).")
        else:
            # Fetch article
            article = fetch_article(url, resolved_url=resolved_url)
            if not article:
                email_results[email_subj]["articles"].append({
                    "url": url,
                    "title": None,
                    "audio": False,
                    "source_type": source_type,
                })
                continue

        title = article["title"]
        print(f"  📄 \"{title}\" ({len(article['text'])} chars)")

        # In dry-run mode, skip all summarization and only save fetched text.
        if dry_run:
            summary = ""
            word_count = len(article["text"].split())
            is_long = word_count > config.ARTICLE_WORD_LIMIT
            body_text = article["text"]
        else:
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

        # Save text output
        filename = f"{i:03d}_{_sanitize_filename(title)}"
        text_file = text_dir / f"{filename}.txt"
        if dry_run:
            text_file.write_text(
                f"Title: {title}\n"
                f"URL: {article['url']}\n\n"
                f"--- Full Article ---\n{article['text']}\n",
                encoding="utf-8",
            )
        elif is_long:
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
            email_results[email_subj]["articles"].append({
                "url": url,
                "title": title,
                "audio": False,
                "source_type": source_type,
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

        email_results[email_subj]["articles"].append({
            "url": url,
            "title": title,
            "audio": audio_ok,
            "source_type": source_type,
        })

    # 4. Write per-email summary report
    _write_summary_report(email_results, out_dir)

    print(f"\n🎉 Done! Generated {success_count} audio file(s) in {mp3_dir}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("🔍 DRY RUN MODE — no emails will be marked as read, no audio generated.\n")
    run(dry_run=dry)
