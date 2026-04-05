import json
import tempfile
import unittest
from pathlib import Path

from main import _write_summary_report


class SummaryReportTests(unittest.TestCase):
    def test_summary_report_mentions_parser_for_each_email(self):
        email_results = {
            "Robinhood Snacks": {
                "parser_name": "robinhood",
                "articles": [
                    {
                        "url": "gmail://message/1#story-1",
                        "title": "Story One",
                        "audio": True,
                        "source_type": "email_story",
                    }
                ],
            },
            "Daily Links": {
                "parser_name": None,
                "articles": [
                    {
                        "url": "https://example.com/article",
                        "title": "External Story",
                        "audio": False,
                        "source_type": "external_url",
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            _write_summary_report(email_results, out_dir)

            summary_text = (out_dir / "summary.txt").read_text(encoding="utf-8")
            summary_json = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))

        self.assertIn("📧 Robinhood Snacks", summary_text)
        self.assertIn("   Parser: robinhood", summary_text)
        self.assertIn("📧 Daily Links", summary_text)
        self.assertIn("   Parser: default", summary_text)
        self.assertEqual(summary_json[0]["parser_name"], "robinhood")
        self.assertEqual(summary_json[1]["parser_name"], "default")


if __name__ == "__main__":
    unittest.main()
