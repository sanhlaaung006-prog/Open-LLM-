import unittest
from unittest import mock

import _bootstrap  # noqa: F401
from openllm_tools.web import dispatch, tool_names
from openllm_tools.web.fetch import FetchResult
from openllm_tools.web.schemas import as_anthropic_tools, as_openai_tools


class SchemaTests(unittest.TestCase):
    def test_tool_names(self):
        self.assertEqual(tool_names(), ["web_fetch", "web_search"])

    def test_openai_shape(self):
        tools = as_openai_tools()
        self.assertEqual(len(tools), 2)
        for tool in tools:
            self.assertEqual(tool["type"], "function")
            fn = tool["function"]
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertEqual(fn["parameters"]["type"], "object")
            self.assertIn("required", fn["parameters"])

    def test_anthropic_shape(self):
        tools = as_anthropic_tools()
        self.assertEqual({t["name"] for t in tools}, {"web_fetch", "web_search"})
        for tool in tools:
            self.assertEqual(tool["input_schema"]["type"], "object")

    def test_schemas_are_independent_copies(self):
        as_openai_tools()[0]["function"]["parameters"]["properties"]["url"]["type"] = "number"
        self.assertEqual(
            as_openai_tools()[0]["function"]["parameters"]["properties"]["url"]["type"],
            "string",
        )

    def test_dispatch_unknown_tool(self):
        result = dispatch("nope", {})
        self.assertFalse(result["ok"])
        self.assertIn("web_fetch", result["error"])

    def test_dispatch_fetch_requires_url(self):
        self.assertFalse(dispatch("web_fetch", {})["ok"])
        self.assertFalse(dispatch("web_fetch", {"url": "  "})["ok"])

    def test_dispatch_fetch_passes_arguments(self):
        fake = FetchResult(url="https://example.com", ok=True, text="hi", title="T")
        with mock.patch("openllm_tools.web.schemas.fetch_url", return_value=fake) as patched:
            result = dispatch("web_fetch", {"url": " https://example.com ", "max_chars": 500})
        patched.assert_called_once_with("https://example.com", max_chars=500)
        self.assertTrue(result["ok"])
        self.assertEqual(result["text"], "hi")

    def test_dispatch_fetch_ignores_unknown_keys(self):
        fake = FetchResult(url="u", ok=True, text="")
        with mock.patch("openllm_tools.web.schemas.fetch_url", return_value=fake) as patched:
            dispatch("web_fetch", {"url": "u", "bogus": 1})
        patched.assert_called_once_with("u")

    def test_dispatch_search_reports_api_errors(self):
        from openllm_tools.web import BraveAuthError

        with mock.patch(
            "openllm_tools.web.schemas.brave_search", side_effect=BraveAuthError("no key")
        ):
            result = dispatch("web_search", {"query": "q"})
        self.assertFalse(result["ok"])
        self.assertIn("no key", result["error"])

    def test_dispatch_search_success(self):
        response = mock.Mock()
        response.to_dict.return_value = {"query": "q", "results": []}
        with mock.patch("openllm_tools.web.schemas.brave_search", return_value=response) as fn:
            result = dispatch("web_search", {"query": "q", "count": 3})
        fn.assert_called_once_with("q", count=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["query"], "q")


if __name__ == "__main__":
    unittest.main()
