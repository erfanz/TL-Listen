import re
import unittest

import config
from extract_links import extract_links_with_details


class LinkParserTests(unittest.TestCase):
    def setUp(self):
        self.original_rules = config.LINK_PARSER_SENDER_RULES

    def tearDown(self):
        config.LINK_PARSER_SENDER_RULES = self.original_rules

    def test_hackernews_digest_parser_keeps_only_direct_tr_th_a_links(self):
        config.LINK_PARSER_SENDER_RULES = [
            (re.compile(r"hndigest\.com", re.IGNORECASE), "hackernews_digest")
        ]
        email = {
            "from": "Hacker News Digest <digest@hndigest.com>",
            "html": """
            <table>
                <tr>
                    <th><a href="https://example.com/articles/story-one-long-path">Story one</a></th>
                </tr>
                <tr>
                    <th><a href="https://example.com/articles/story-two-long-path">Story two</a></th>
                </tr>
                <tr>
                    <th><span><a href="https://example.com/articles/ignored-nested-link-path">Ignore nested</a></span></th>
                </tr>
                <tr>
                    <td><a href="https://example.com/articles/ignored-table-data-link">Ignore td link</a></td>
                </tr>
            </table>
            <p><a href="https://example.com/articles/ignored-paragraph-link">Ignore paragraph link</a></p>
            """,
            "text": "https://example.com/articles/ignored-plain-text-link",
        }

        details = extract_links_with_details(email)

        self.assertEqual(
            details["article_urls"],
            [
                "https://example.com/articles/story-one-long-path",
                "https://example.com/articles/story-two-long-path",
            ],
        )
        self.assertEqual(details["raw_count"], 2)
        self.assertEqual(details["unique_cleaned_count"], 2)

    def test_default_link_extraction_still_runs_without_matching_specialized_rule(self):
        config.LINK_PARSER_SENDER_RULES = [
            (re.compile(r"hndigest\.com", re.IGNORECASE), "hackernews_digest")
        ]
        email = {
            "from": "Other Digest <digest@example.com>",
            "html": """
            <p><a href="https://example.com/articles/default-extractor-link-path">Paragraph link</a></p>
            """,
            "text": "",
        }

        details = extract_links_with_details(email)

        self.assertEqual(
            details["article_urls"],
            ["https://example.com/articles/default-extractor-link-path"],
        )


if __name__ == "__main__":
    unittest.main()
