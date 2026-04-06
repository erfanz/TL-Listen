from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

from fetch_feeds import (
    filter_feed_entries,
    get_feed_checkpoint,
    load_feed_state,
    save_feed_state,
    set_feed_checkpoint,
)


class RssFeedTests(unittest.TestCase):
    def test_first_run_uses_initial_window_days(self):
        now = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
        entries = [
            {
                "title": "Fresh story",
                "link": "https://example.com/fresh",
                "published": "Sat, 04 Apr 2026 12:00:00 GMT",
            },
            {
                "title": "Old story",
                "link": "https://example.com/old",
                "published": "Fri, 27 Mar 2026 12:00:00 GMT",
            },
        ]

        filtered, checkpoint = filter_feed_entries(
            entries,
            checkpoint=None,
            now=now,
            initial_window_days=7,
        )

        self.assertEqual(checkpoint, datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc))
        self.assertEqual([item["url"] for item in filtered], ["https://example.com/fresh"])

    def test_checkpoint_filters_out_older_entries(self):
        checkpoint = datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc)
        entries = [
            {
                "title": "Before checkpoint",
                "link": "https://example.com/before",
                "published": "Wed, 01 Apr 2026 12:00:00 GMT",
            },
            {
                "title": "After checkpoint",
                "link": "https://example.com/after",
                "published": "Thu, 03 Apr 2026 12:00:00 GMT",
            },
        ]

        filtered, effective_checkpoint = filter_feed_entries(entries, checkpoint=checkpoint)

        self.assertEqual(effective_checkpoint, checkpoint)
        self.assertEqual([item["title"] for item in filtered], ["After checkpoint"])

    def test_state_round_trip_persists_last_published(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "rss_state.json"
            state = load_feed_state(state_path)
            checkpoint = datetime(2026, 4, 5, 15, 30, tzinfo=timezone.utc)

            set_feed_checkpoint(state, "https://example.com/feed.xml", checkpoint)
            save_feed_state(state, state_path)
            reloaded = load_feed_state(state_path)

        self.assertEqual(
            get_feed_checkpoint(reloaded, "https://example.com/feed.xml"),
            checkpoint,
        )


if __name__ == "__main__":
    unittest.main()
