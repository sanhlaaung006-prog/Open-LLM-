import unittest

import _bootstrap  # noqa: F401  (adds src/ to sys.path)
from openllm_tools.web.html2text import extract_title, html_to_text


class HtmlToTextTests(unittest.TestCase):
    def test_extracts_and_normalises_title(self):
        doc = html_to_text("<html><head><title>  Hello \n  World </title></head><body></body></html>")
        self.assertEqual(doc.title, "Hello World")

    def test_headings_links_and_lists(self):
        html = (
            "<h2>Section</h2>"
            '<p>See <a href="https://example.com/a">the docs</a>.</p>'
            "<ul><li>one</li><li>two</li></ul>"
            "<ol><li>first</li></ol>"
        )
        text = html_to_text(html).text
        self.assertIn("## Section", text)
        self.assertIn("[the docs](https://example.com/a)", text)
        self.assertIn("- one", text)
        self.assertIn("1. first", text)

    def test_anchor_without_href_is_plain_text(self):
        text = html_to_text('<p><a name="x">anchor</a> text</p>').text
        self.assertEqual(text, "anchor text")
        self.assertNotIn("]", text)

    def test_scripts_and_styles_are_dropped(self):
        html = (
            "<html><head><style>p{color:red}</style></head><body>"
            "<script>alert('x')</script><p>Visible</p></body></html>"
        )
        text = html_to_text(html).text
        self.assertIn("Visible", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("color:red", text)

    def test_pre_whitespace_preserved(self):
        text = html_to_text("<pre>a\n    b</pre>").text
        self.assertIn("a\n    b", text)
        self.assertIn("```", text)

    def test_inline_code_and_emphasis(self):
        text = html_to_text("<p>Use <code>print()</code> and <strong>care</strong>.</p>").text
        self.assertIn("`print()`", text)
        self.assertIn("**care**", text)

    def test_entities_are_decoded(self):
        text = html_to_text("<p>Tom &amp; Jerry &lt;3</p>").text
        self.assertEqual(text, "Tom & Jerry <3")

    def test_blank_runs_collapse(self):
        text = html_to_text("<p>a</p><div></div><div></div><p>b</p>").text
        self.assertNotIn("\n\n\n", text)

    def test_malformed_html_does_not_raise(self):
        doc = html_to_text("<p>unclosed <b>bold <div><span>x")
        self.assertIn("unclosed", doc.text)

    def test_extract_title_helper(self):
        self.assertEqual(extract_title("<title>T</title>"), "T")
        self.assertIsNone(extract_title("<p>no title</p>"))


if __name__ == "__main__":
    unittest.main()
