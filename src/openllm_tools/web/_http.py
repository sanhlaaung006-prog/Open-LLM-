"""A small, dependency-free HTTP client for the web tools.

Only what a web tool actually needs:

* ``GET`` / ``POST`` with custom headers and a connect timeout
* transparent ``gzip`` / ``deflate`` decoding
* a cap on how many bytes are read into memory
* a guard that refuses to talk to loopback / private / link-local hosts
  (the classic SSRF foot-gun when an LLM chooses the URL)

Everything else (parsing, truncation, shaping) lives in :mod:`fetch` and
:mod:`brave`.
"""

from __future__ import annotations

import gzip
import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "BlockedAddressError",
    "HttpStatusError",
    "Response",
    "WebToolError",
    "request",
]

DEFAULT_USER_AGENT = (
    "openllm-tools/0.1 (+https://github.com/sanhlaaung006-prog/Open-LLM-)"
)
DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB
ALLOWED_SCHEMES = ("http", "https")


class WebToolError(Exception):
    """Base class for every error raised by the web tools."""


class BlockedAddressError(WebToolError):
    """Raised when a URL resolves to a private / reserved address."""


class HttpStatusError(WebToolError):
    """Raised when the server answers with an HTTP error status."""

    def __init__(self, status: int, url: str, body: bytes = b"") -> None:
        self.status = status
        self.url = url
        self.body = body
        snippet = body[:300].decode("utf-8", "replace").strip()
        message = f"HTTP {status} for {url}"
        if snippet:
            message = f"{message}: {snippet}"
        super().__init__(message)


@dataclass
class Response:
    """A decoded HTTP response."""

    url: str
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    truncated: bool = False

    @property
    def content_type(self) -> str:
        """The bare media type, e.g. ``text/html``."""
        raw = self.headers.get("content-type", "")
        return raw.split(";", 1)[0].strip().lower()

    @property
    def charset(self) -> str:
        raw = self.headers.get("content-type", "")
        for part in raw.split(";")[1:]:
            key, _, value = part.partition("=")
            if key.strip().lower() == "charset":
                return value.strip().strip("'\"") or "utf-8"
        return "utf-8"

    def text(self) -> str:
        """Decode the body using the declared charset, falling back to UTF-8."""
        try:
            return self.body.decode(self.charset, "replace")
        except LookupError:  # unknown charset name
            return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.text())

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def _decode_body(raw: bytes, encoding: str) -> bytes:
    encoding = (encoding or "").strip().lower()
    if encoding in ("gzip", "x-gzip"):
        try:
            return gzip.decompress(raw)
        except OSError as exc:
            raise WebToolError(f"Could not decompress gzip response: {exc}") from exc
    if encoding == "deflate":
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                return zlib.decompress(raw, wbits)
            except zlib.error:
                continue
        raise WebToolError("Could not decompress deflate response")
    return raw


def _is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return addr.is_global


def assert_public_host(host: str) -> None:
    """Fail loudly if ``host`` resolves anywhere non-public.

    This blocks loopback, RFC1918, link-local (cloud metadata!), CGNAT,
    reserved and unspecified addresses.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise WebToolError(f"Could not resolve host {host!r}: {exc}") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise WebToolError(f"Could not resolve host {host!r}")

    blocked = sorted(ip for ip in addresses if not _is_public(ip))
    if blocked:
        raise BlockedAddressError(
            f"Refusing to fetch {host!r}: it resolves to non-public address(es) "
            f"{', '.join(blocked)}. Pass allow_private=True to override."
        )


def _clean_headers(raw_headers: Mapping[str, str]) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in raw_headers.items()}


def request(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    data: bytes | str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    user_agent: str = DEFAULT_USER_AGENT,
    allow_private: bool = False,
) -> Response:
    """Perform an HTTP request and return a decoded :class:`Response`."""
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise WebToolError(
            f"Unsupported URL scheme {scheme or '(none)'!r}; use http or https."
        )
    if not parsed.hostname:
        raise WebToolError(f"URL is missing a host name: {url!r}")

    if not allow_private:
        assert_public_host(parsed.hostname)

    if isinstance(data, str):
        data = data.encode("utf-8")

    merged = {
        "User-Agent": user_agent,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
    }
    for key, value in (headers or {}).items():
        merged[key] = value

    req = urllib.request.Request(
        url, data=data, headers=merged, method=method.upper()
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            resp_headers = _clean_headers(dict(resp.headers.items()))
            raw = resp.read(max_bytes + 1) or b""
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            final_url = resp.geturl() or url
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(4096) or b""
        except Exception:  # pragma: no cover - defensive
            body = b""
        raise HttpStatusError(exc.code, exc.geturl() or url, body) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise WebToolError(f"Timed out after {timeout}s fetching {url}") from exc
        raise WebToolError(f"Could not reach {url}: {reason}") from exc
    except (socket.timeout, TimeoutError) as exc:
        raise WebToolError(f"Timed out after {timeout}s fetching {url}") from exc

    body = _decode_body(raw, resp_headers.get("content-encoding", ""))
    if len(body) > max_bytes:
        body = body[:max_bytes]
        truncated = True

    return Response(
        url=final_url,
        status=status,
        headers=resp_headers,
        body=body,
        truncated=truncated,
    )
