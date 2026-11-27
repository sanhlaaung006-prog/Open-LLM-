import json
import os
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import _bootstrap  # noqa: F401
from openllm_tools.web import (
    BraveAPIError,
    BraveAuthError,
    BraveQueryError,
    BraveRateLimitError,
    brave_search,
)
from openllm_tools.web.brave import BRAVE_ENDPOINT, ENV_VAR

SAMPLE = {
    "type": "search",
    "web": {
        "type": "search",
        "results": [
            {
                "title": "Open <strong>LLM</strong> inference",
                "url": "https://example.com/one",
                "description": "Fast <strong>serving</strong> &amp; batching",
                "age": "2 days ago",
                "profile": {"name": "Example"},
                "extra_snippets": ["extra one"],
            },
            {
                "title": "Second hit",
                "url": "https://example.com/two",
                "description": "Another result",
            },
            {"title": "no url", "description": "dropped"},
        ],
    },
    "news": {
        "results": [
            {"title": "Breaking", "url": "https://news.example/n", "age": "1 hour ago",
             "meta_url": {"hostname": "news.example"}},
        ]
    },
    "infobox": {
        "results": [{"title": "LLM", "long_desc": "A large language model.", "url": "https://en.wikipedia.org/wiki/LLM"}]
    },
    "faq": {"results": [{"question": "What is it?", "answer": "A model."}]},
}


class FakeTransport:
    def __init__(self, status=200, payload=None, body=None):
        self.status = status
        self.payload = payload if payload is not None else SAMPLE
        self.body = body
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if self.body is not None:
            return self.status, {"content-type": "application/json"}, self.body
        return self.status, {"content-type": "application/json"}, json.dumps(self.payload).encode()


class BraveSearchTests(unittest.TestCase):
    def test_parses_results(self):
        transport = FakeTransport()
        response = brave_search("open llm", api_key="k", transport=transport)
        self.assertEqual(len(response.results), 2)  # item without url dropped
        first = response.results[0]
        self.assertEqual(first.title, "Open LLM inference")  # tags stripped
        self.assertEqual(first.description, "Fast serving & batching")
        self.assertEqual(first.url, "https://example.com/one")
        self.assertEqual(first.age, "2 days ago")
        self.assertEqual(first.source, "Example")
        self.assertEqual(first.extra_snippets, ["extra one"])

    def test_sends_auth_header_and_params(self):
        transport = FakeTransport()
        brave_search(
            "  spaced   query ", count=7, offset=2, country="mm",
            freshness="pw", safesearch="strict", api_key="secret", transport=transport,
        )
        call = transport.calls[0]
        self.assertEqual(call["headers"]["X-Subscription-Token"], "secret")
        self.assertTrue(call["url"].startswith(BRAVE_ENDPOINT))
        params = parse_qs(urlsplit(call["url"]).query)
        self.assertEqual(params["q"], ["spaced query"])
        self.assertEqual(params["count"], ["7"])
        self.assertEqual(params["offset"], ["2"])
        self.assertEqual(params["country"], ["MM"])
        self.assertEqual(params["freshness"], ["pw"])
        self.assertEqual(params["safesearch"], ["strict"])
        self.assertEqual(params["text_decorations"], ["0"])

    def test_extracts_news_infobox_and_faq(self):
        response = brave_search("q", api_key="k", transport=FakeTransport())
        self.assertEqual(response.news[0].title, "Breaking")
        self.assertEqual(response.infobox["title"], "LLM")
        self.assertEqual(response.faq[0]["question"], "What is it?")
        payload = response.to_dict()
        self.assertIn("news", payload)
        self.assertIn("infobox", payload)

    def test_markdown_rendering(self):
        markdown = brave_search("q", api_key="k", transport=FakeTransport()).as_markdown()
        self.assertIn("## Search results for 'q'", markdown)
        self.assertIn("[Open LLM inference](https://example.com/one)", markdown)
        self.assertIn("### News", markdown)

    def test_empty_result_set(self):
        transport = FakeTransport(payload={"web": {"results": []}})
        response = brave_search("nothing", api_key="k", transport=transport)
        self.assertEqual(response.results, [])
        self.assertIn("No results", response.as_markdown())

    def test_missing_api_key(self):
        with mock.patch.dict(os.environ, {ENV_VAR: ""}):
            with self.assertRaises(BraveAuthError) as ctx:
                brave_search("q", transport=FakeTransport())
        self.assertIn(ENV_VAR, str(ctx.exception))

    def test_key_from_environment(self):
        transport = FakeTransport()
        with mock.patch.dict(os.environ, {ENV_VAR: "env-key"}):
            brave_search("q", transport=transport)
        self.assertEqual(transport.calls[0]["headers"]["X-Subscription-Token"], "env-key")

    def test_401_raises_auth_error(self):
        with self.assertRaises(BraveAuthError):
            brave_search("q", api_key="bad", transport=FakeTransport(status=401))

    def test_429_raises_rate_limit(self):
        with self.assertRaises(BraveRateLimitError):
            brave_search("q", api_key="k", transport=FakeTransport(status=429))

    def test_422_raises_query_error_with_detail(self):
        transport = FakeTransport(status=422, body=b'{"error":"bad param"}')
        with self.assertRaises(BraveQueryError) as ctx:
            brave_search("q", api_key="k", transport=transport)
        self.assertIn("bad param", str(ctx.exception))

    def test_invalid_json_raises_api_error(self):
        with self.assertRaises(BraveAPIError):
            brave_search("q", api_key="k", transport=FakeTransport(body=b"<html>nope"))

    def test_validation(self):
        cases = [
            dict(query="", count=5),
            dict(query="q", count=0),
            dict(query="q", count=21),
            dict(query="q", offset=10),
            dict(query="q", safesearch="maybe"),
            dict(query="q", freshness="sometimes"),
            dict(query="x" * 401),
        ]
        for case in cases:
            kwargs = {k: v for k, v in case.items() if k != "query"}
            with self.subTest(case=case):
                with self.assertRaises(BraveQueryError):
                    brave_search(case.get("query", "q"), api_key="k",
                                 transport=FakeTransport(), **kwargs)


if __name__ == "__main__":
    unittest.main()
