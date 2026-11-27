import unittest

import _bootstrap  # noqa: F401
from _server import LocalSite
from openllm_tools.web import fetch_url


class FetchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = LocalSite().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.site.__exit__(None, None, None)

    def test_html_page_is_converted(self):
        result = fetch_url(self.site.url("/page"), allow_private=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.status, 200)
        self.assertEqual(result.content_type, "text/html")
        self.assertEqual(result.title, "Test Page — Local")
        self.assertIn("# Hello Local", result.text)
        self.assertIn("[link](https://example.com/next)", result.text)
        self.assertNotIn("should-not-appear", result.text)

    def test_raw_html_is_returned_verbatim(self):
        result = fetch_url(self.site.url("/page"), allow_private=True, raw_html=True)
        self.assertTrue(result.ok)
        self.assertIn("<html>", result.text)
        self.assertIn("should-not-appear", result.text)

    def test_json_is_pretty_printed(self):
        result = fetch_url(self.site.url("/json"), allow_private=True)
        self.assertTrue(result.ok)
        self.assertIn('"b": 2', result.text)

    def test_plain_text_passthrough(self):
        result = fetch_url(self.site.url("/text"), allow_private=True)
        self.assertEqual(result.text, "plain text body")

    def test_redirect_is_followed(self):
        result = fetch_url(self.site.url("/redirect"), allow_private=True)
        self.assertTrue(result.ok)
        self.assertTrue(result.final_url.endswith("/page"))

    def test_404_is_a_soft_failure(self):
        result = fetch_url(self.site.url("/missing"), allow_private=True)
        self.assertFalse(result.ok)
        self.assertEqual(result.status, 404)
        self.assertIn("404", result.error)
        self.assertIn("Not found here", result.error)
        self.assertIn("Fetch failed", result.as_markdown())

    def test_binary_content_is_rejected(self):
        result = fetch_url(self.site.url("/binary"), allow_private=True)
        self.assertFalse(result.ok)
        self.assertIn("Unsupported content type", result.error)

    def test_max_chars_truncates_with_marker(self):
        result = fetch_url(self.site.url("/big"), allow_private=True, max_chars=100)
        self.assertTrue(result.ok)
        self.assertTrue(result.truncated)
        self.assertLess(len(result.text), 200)
        self.assertIn("truncated", result.text)

    def test_zero_max_chars_means_no_limit(self):
        result = fetch_url(self.site.url("/big"), allow_private=True, max_chars=0)
        self.assertEqual(len(result.text), 50_000)

    def test_private_addresses_blocked_by_default(self):
        result = fetch_url(self.site.url("/page"))
        self.assertFalse(result.ok)
        self.assertIn("non-public", result.error)

    def test_private_addresses_allowed_on_request(self):
        result = fetch_url(self.site.url("/page"), allow_private=True)
        self.assertTrue(result.ok)

    def test_unsupported_scheme(self):
        result = fetch_url("file:///etc/passwd")
        self.assertFalse(result.ok)
        self.assertIn("scheme", result.error)

    def test_url_without_host(self):
        result = fetch_url("http://")
        self.assertFalse(result.ok)

    def test_dns_failure_is_soft(self):
        result = fetch_url("https://does-not-exist.invalid/", timeout=5)
        self.assertFalse(result.ok)
        self.assertIn("resolve", result.error)

    def test_markdown_includes_title_and_source(self):
        result = fetch_url(self.site.url("/page"), allow_private=True)
        markdown = result.as_markdown()
        self.assertTrue(markdown.startswith("# Test Page — Local"))
        self.assertIn("Source: http://127.0.0.1", markdown)

    def test_result_is_truthy_only_on_success(self):
        self.assertTrue(fetch_url(self.site.url("/page"), allow_private=True))
        self.assertFalse(fetch_url(self.site.url("/missing"), allow_private=True))


if __name__ == "__main__":
    unittest.main()
