from datetime import datetime

import config
from fetch_articles import fetch_article
from summarize import summarize, summarize_extended
from text_to_speech import generate_article_audio

from shared.reporting import sanitize_filename
import re


def create_dated_output_dirs(output_root, *subdirs):
    """Create the standard date-based output directory structure."""
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = output_root / today
    out_dir.mkdir(parents=True, exist_ok=True)

    created_dirs = {}
    for subdir in subdirs:
        path = out_dir / subdir
        path.mkdir(parents=True, exist_ok=True)
        created_dirs[subdir] = path

    return today, out_dir, created_dirs


def process_article_queue(
    all_articles,
    *,
    text_dir,
    mp3_dir,
    dry_run,
    group_results,
    group_key_field,
):
    """
    Process queued items into text output and audio.

    Each item should include:
      - url
      - resolved_url (optional)
      - source_type (optional)
      - <group_key_field>
      - text_override (optional)
      - title_hint (optional)
      - source_name (optional)
    """
    success_count = 0
    for index, item in enumerate(all_articles, 1):
        url = item["url"]
        resolved_url = item.get("resolved_url", url)
        group_key = item[group_key_field]
        source_type = item.get("source_type", "external_url")
        source_name = item.get("source_name")
        if source_name:
            match = re.match(r'\s*"?([^"<]*)"?\s*<.*?>', source_name)
            if match:
                source_name = match.group(1).strip() or source_name.strip()
            else:
                source_name = source_name.strip()

        print(f"[{index}/{len(all_articles)}] {url}")

        if item.get("text_override"):
            article = {
                "url": url,
                "original_url": url,
                "title": item.get("title_hint") or "Inline story",
                "text": item["text_override"],
            }
            print("  📨 Using inline story content (no external fetch).")
        else:
            article = fetch_article(url, resolved_url=resolved_url)
            if not article:
                group_results[group_key]["articles"].append(
                    {
                        "url": url,
                        "title": None,
                        "audio": False,
                        "source_type": source_type,
                    }
                )
                continue

        title = article["title"]
        print(f"  📄 \"{title}\" ({len(article['text'])} chars)")
        article_word_count = len(article["text"].split())

        if dry_run:
            summary = ""
            summary_word_count = 0
            extended_summary_word_count = 0
            is_long = article_word_count > config.ARTICLE_WORD_LIMIT
            body_text = article["text"]
        else:
            print("  🤖 Summarizing...")
            summary = summarize(article["text"], title=title)
            print(f"  📝 Summary: {summary[:100]}...")
            summary_word_count = len(summary.split())

            is_long = article_word_count > config.ARTICLE_WORD_LIMIT
            if is_long:
                print(
                    f"  📏 Article is {article_word_count} words (>{config.ARTICLE_WORD_LIMIT}) — generating extended summary..."
                )
                body_text = summarize_extended(article["text"], title=title)
                extended_summary_word_count = len(body_text.split())
            else:
                body_text = article["text"]
                extended_summary_word_count = 0

        filename = f"{index:03d}_{sanitize_filename(title)}"
        text_file = text_dir / f"{filename}.txt"

        # Build header with optional source name
        header = f"Title: {title}\n"
        if source_name:
            header += f"Source: {source_name}\n"
        header += f"URL: {article['url']}\n\n"

        if dry_run:
            text_file.write_text(
                f"{header}"
                f"--- Full Article ---\n{article['text']}\n",
                encoding="utf-8",
            )
        elif is_long:
            text_file.write_text(
                f"{header}"
                f"--- Summary ({summary_word_count} words) ---\n{summary}\n\n"
                f"--- Extended Summary ({extended_summary_word_count} words; article was {article_word_count} words) ---\n{body_text}\n",
                encoding="utf-8",
            )
        else:
            text_file.write_text(
                f"{header}"
                f"--- Summary ({summary_word_count} words) ---\n{summary}\n\n"
                f"--- Full Article ---\n{article['text']}\n",
                encoding="utf-8",
            )
        print(f"  💾 {text_file}")

        if dry_run:
            print("  ⏭️  Dry run — skipping audio generation.\n")
            group_results[group_key]["articles"].append(
                {
                    "url": url,
                    "title": title,
                    "audio": False,
                    "source_type": source_type,
                }
            )
            continue

        output_path = mp3_dir / filename
        print("  🎙️  Generating audio...")
        audio_ok = False
        try:
            result_file = generate_article_audio(
                source_name,
                title,
                summary,
                body_text,
                output_path,
                is_long=is_long,
            )
            print(f"  ✅ {result_file}\n")
            audio_ok = True
            success_count += 1
        except Exception as exc:
            print(f"  ❌ Audio generation failed: {exc}\n")

        group_results[group_key]["articles"].append(
            {
                "url": url,
                "title": title,
                "audio": audio_ok,
                "source_type": source_type,
            }
        )

    return success_count
