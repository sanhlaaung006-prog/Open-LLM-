import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _bootstrap  # noqa: F401
from _server import LocalSite
from openllm_tools.web.cli import main


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = LocalSite().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.site.__exit__(None, None, None)

    def test_fetch_markdown(self):
        code, out, _ = run(["fetch", self.site.url("/page"), "--allow-private"])
        self.assertEqual(code, 0)
        self.assertIn("# Test Page — Local", out)
        self.assertIn("Source: http://127.0.0.1", out)

    def test_fetch_json(self):
        code, out, _ = run(["fetch", self.site.url("/page"), "--allow-private", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["title"], "Test Page — Local")

    def test_fetch_json_no_text(self):
        code, out, _ = run(
            ["fetch", self.site.url("/page"), "--allow-private", "--json", "--no-text"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["text"], "")

    def test_fetch_failure_exit_code(self):
        code, out, err = run(["fetch", self.site.url("/missing"), "--allow-private"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("error:", err)

    def test_max_chars_flag(self):
        code, out, _ = run(
            ["fetch", self.site.url("/big"), "--allow-private", "--max-chars", "50", "--json"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["truncated"])

    def test_tools_formats(self):
        for fmt in ("names", "openai", "anthropic"):
            with self.subTest(fmt=fmt):
                code, out, _ = run(["tools", "--format", fmt])
                self.assertEqual(code, 0)
                self.assertIn("tools", json.loads(out))

        code, out, _ = run(["tools", "--format", "openai"])
        names = [t["function"]["name"] for t in json.loads(out)["tools"]]
        self.assertEqual(names, ["web_fetch", "web_search"])

    def test_doctor_runs(self):
        code, out, _ = run(["doctor"])
        self.assertEqual(code, 0)
        self.assertIn("openllm_tools.web", out)
        self.assertIn("BRAVE_API_KEY", out)

    def test_search_without_key_fails_cleanly(self):
        import os
        from unittest import mock

        from openllm_tools.web.brave import ENV_VAR

        with mock.patch.dict(os.environ, {ENV_VAR: ""}):
            code, out, err = run(["search", "anything"])
        self.assertEqual(code, 1)
        self.assertIn(ENV_VAR, err)

    def test_missing_subcommand_is_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            run([])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
