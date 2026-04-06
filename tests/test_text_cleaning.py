import unittest

from shared.text_cleaning import decode_http_text, normalize_title, repair_mojibake, strip_emojis


class _FakeResponse:
    def __init__(self, content, *, headers=None, encoding="ISO-8859-1", apparent_encoding="utf-8", text=""):
        self.content = content
        self.headers = headers or {}
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding
        self.text = text


class TextCleaningTests(unittest.TestCase):
    def test_repair_mojibake_restores_utf8_emoji(self):
        self.assertEqual(
            repair_mojibake("ðº Google just gave away its best AI"),
            "😺 Google just gave away its best AI",
        )

    def test_strip_emojis_removes_title_emoji(self):
        self.assertEqual(
            strip_emojis("😺 Google just gave away its best AI"),
            "Google just gave away its best AI",
        )

    def test_normalize_title_repairs_then_strips_emoji(self):
        self.assertEqual(
            normalize_title("ðº Marc Andreessen just described your future coworker"),
            "Marc Andreessen just described your future coworker",
        )

    def test_repair_mojibake_leaves_normal_text_unchanged(self):
        self.assertEqual(
            repair_mojibake("OpenAI just gave away its best AI"),
            "OpenAI just gave away its best AI",
        )

    def test_decode_http_text_prefers_utf8_when_charset_missing(self):
        response = _FakeResponse(
            "😺 Google just gave away its best AI".encode("utf-8"),
            headers={"content-type": "text/html"},
        )
        self.assertEqual(
            decode_http_text(response),
            "😺 Google just gave away its best AI",
        )


if __name__ == "__main__":
    unittest.main()
