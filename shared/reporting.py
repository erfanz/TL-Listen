import json


def sanitize_filename(text, max_len=60):
    """Create a filesystem-safe filename from text."""
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return safe.strip().replace(" ", "_")[:max_len] or "article"


def write_summary_report(
    group_results,
    out_dir,
    *,
    heading_title,
    group_icon,
    metadata_label,
    metadata_key,
    metadata_default,
    group_json_key,
):
    """Write a per-group summary report (text table + JSON) to the output dir."""
    report_path = out_dir / "summary.txt"
    json_path = out_dir / "summary.json"

    lines = ["=" * 80, f"  {heading_title}", "=" * 80, ""]

    json_data = []
    for group_name, group_result in group_results.items():
        display_name = group_result.get("display_name") or group_name
        metadata_value = group_result.get(metadata_key) or metadata_default
        articles = group_result["articles"]
        lines.append(f"{group_icon} {display_name}")
        lines.append(f"   {metadata_label}: {metadata_value}")
        lines.append("-" * 80)
        lines.append(f"  {'#':<4} {'Source':<12} {'Article Title':<28} {'Audio':>6}  URL")
        lines.append(f"  {'—'*3:<4} {'—'*10:<12} {'—'*26:<28} {'—'*5:>6}  {'—'*28}")

        group_json = {
            group_json_key: display_name,
            metadata_key: metadata_value,
            "articles": [],
        }
        for idx, art in enumerate(articles, 1):
            title_display = (art["title"] or "⚠️ Failed to fetch")[:26]
            source_display = (art.get("source_type") or "external_url")[:10]
            audio_flag = "  ✅" if art["audio"] else "  ❌"
            lines.append(
                f"  {idx:<4} {source_display:<12} {title_display:<28} {audio_flag:>6}  {art['url']}"
            )
            group_json["articles"].append(
                {
                    "url": art["url"],
                    "title": art["title"],
                    "audio_produced": art["audio"],
                    "source_type": art.get("source_type", "external_url"),
                }
            )

        total = len(articles)
        audio_count = sum(1 for article in articles if article["audio"])
        fetched_count = sum(1 for article in articles if article["title"])
        lines.append("")
        lines.append(f"  Total: {total} item(s) | {fetched_count} fetched | {audio_count} audio file(s)")
        lines.append("")
        json_data.append(group_json)

    report_text = "\n".join(lines) + "\n"
    report_path.write_text(report_text, encoding="utf-8")
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\n📊 Summary report saved to {report_path}")
    print(f"   JSON data saved to {json_path}")
    print()
    print(report_text)
