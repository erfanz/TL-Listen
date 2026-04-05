import unittest

from email_processing import trim_html_for_llm


class TrimHtmlForLlmTests(unittest.TestCase):
    def test_removes_scripts_styles_unwraps_layout_tags_and_strips_attributes(self):
        html = """
        <div class="outer">
            <script type="text/javascript">bad()</script>
            <table id="layout">
                <tbody>
                    <tr>
                        <td data-cell="1">
                            <a href="https://example.com" class="cta">Read more</a>
                        </td>
                    </tr>
                </tbody>
            </table>
            <style>.outer { color: red; }</style>
            <!-- comment -->
            <section data-block="story">
                <h2 class="headline">Headline</h2>
            </section>
        </div>
        """

        trimmed = trim_html_for_llm(html)

        self.assertEqual(
            trimmed,
            '<a>Read more</a><section><h2>Headline</h2></section>',
        )

    def test_removes_empty_elements_left_after_cleanup(self):
        html = """
        <div>
            <u></u>
            <span> </span>
            <div><span></span></div>
            <p>Keep me</p>
        </div>
        """

        trimmed = trim_html_for_llm(html)

        self.assertEqual(trimmed, "<p>Keep me</p>")


if __name__ == "__main__":
    unittest.main()
