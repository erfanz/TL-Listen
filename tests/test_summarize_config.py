import unittest
from unittest.mock import patch

import config
from summarize import (
    _count_words,
    _extended_summary_system_prompt,
    _extended_summary_token_budget,
    _fallback_extended_summary,
    _fallback_summary,
    _summary_system_prompt,
    summarize_extended,
)


class SummarizeConfigTests(unittest.TestCase):
    def setUp(self):
        self.original_sentence_count = config.SUMMARY_SENTENCE_COUNT
        self.original_summary_max_tokens = config.SUMMARY_MAX_TOKENS
        self.original_extended_word_count = config.EXTENDED_SUMMARY_WORD_COUNT
        self.original_extended_max_tokens = config.EXTENDED_SUMMARY_MAX_TOKENS

    def tearDown(self):
        config.SUMMARY_SENTENCE_COUNT = self.original_sentence_count
        config.SUMMARY_MAX_TOKENS = self.original_summary_max_tokens
        config.EXTENDED_SUMMARY_WORD_COUNT = self.original_extended_word_count
        config.EXTENDED_SUMMARY_MAX_TOKENS = self.original_extended_max_tokens

    def test_summary_prompt_uses_configured_sentence_count(self):
        config.SUMMARY_SENTENCE_COUNT = 6

        prompt = _summary_system_prompt()

        self.assertIn("about 6 sentences", prompt)

    def test_extended_summary_prompt_uses_configured_word_count(self):
        config.EXTENDED_SUMMARY_WORD_COUNT = 600

        prompt = _extended_summary_system_prompt()

        self.assertIn("no more than 600 words", prompt)

    def test_extended_summary_token_budget_tracks_word_count(self):
        config.EXTENDED_SUMMARY_WORD_COUNT = 200
        config.EXTENDED_SUMMARY_MAX_TOKENS = 600

        self.assertEqual(_extended_summary_token_budget(), 300)

    def test_extended_summary_token_budget_respects_configured_cap(self):
        config.EXTENDED_SUMMARY_WORD_COUNT = 600
        config.EXTENDED_SUMMARY_MAX_TOKENS = 300

        self.assertEqual(_extended_summary_token_budget(), 300)

    def test_fallback_summary_uses_configured_sentence_count(self):
        config.SUMMARY_SENTENCE_COUNT = 2

        summary = _fallback_summary("One. Two. Three. Four.")

        self.assertEqual(summary, "One. Two.")

    def test_fallback_extended_summary_uses_configured_word_count(self):
        config.EXTENDED_SUMMARY_WORD_COUNT = 3

        summary = _fallback_extended_summary("one two three four five")

        self.assertEqual(summary, "one two three")

    def test_summarize_extended_rewrites_when_initial_summary_is_too_long(self):
        config.EXTENDED_SUMMARY_WORD_COUNT = 5
        config.EXTENDED_SUMMARY_MAX_TOKENS = 100

        class _MockResponse:
            def __init__(self, text):
                self._text = text

            def raise_for_status(self):
                return None

            def json(self):
                return {"response": self._text}

        responses = [
            _MockResponse("one two three four five six seven"),
            _MockResponse("one two three four five"),
        ]

        with patch("summarize.requests.post", side_effect=responses) as mock_post:
            summary = summarize_extended("article body", title="Example")

        self.assertEqual(summary, "one two three four five")
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(_count_words(summary), 5)

    def test_summarize_extended_falls_back_after_rewrite_still_exceeds_limit(self):
        config.EXTENDED_SUMMARY_WORD_COUNT = 4
        config.EXTENDED_SUMMARY_MAX_TOKENS = 100

        class _MockResponse:
            def __init__(self, text):
                self._text = text

            def raise_for_status(self):
                return None

            def json(self):
                return {"response": self._text}

        responses = [
            _MockResponse("one two three four five six"),
            _MockResponse("one two three four five"),
            _MockResponse("one two three four five"),
        ]

        with patch("summarize.requests.post", side_effect=responses) as mock_post:
            summary = summarize_extended("alpha beta gamma delta epsilon zeta", title="Example")

        self.assertEqual(summary, "alpha beta gamma delta")
        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(_count_words(summary), 4)


if __name__ == "__main__":
    unittest.main()
