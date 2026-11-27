"""A tiny local web site used by the tests (no network access required)."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html>
<html>
<head>
  <title>Test Page &mdash; Local</title>
  <style>body { color: red }</style>
  <script>window.secret = "should-not-appear";</script>
</head>
<body>
  <h1>Hello Local</h1>
  <p>First paragraph with a <a href="https://example.com/next">link</a>.</p>
  <ul><li>alpha</li><li>beta</li></ul>
  <pre>line1
    indented</pre>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence the test output
        pass

    def _send(self, status: int, ctype: str, body: bytes, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):  # pragma: no cover - unused, kept for completeness
        self._send(200, "text/html", b"")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/page":
            self._send(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        elif path == "/json":
            self._send(200, "application/json", b'{"b":2,"a":[1,2,3]}')
        elif path == "/text":
            self._send(200, "text/plain; charset=utf-8", b"plain text body")
        elif path == "/binary":
            self._send(200, "application/octet-stream", b"\x00\x01\x02")
        elif path == "/big":
            self._send(200, "text/plain", ("x" * 50_000).encode())
        elif path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._send(404, "text/html", b"<html><body>Not found here</body></html>")


class LocalSite:
    """Context manager that serves :data:`PAGE` on a random loopback port."""

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def __enter__(self) -> "LocalSite":
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
