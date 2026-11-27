"""Web page fetcher for LLM agents.

Public API::

    from openllm_tools.web import fetch_url

    result = fetch_url("https://example.com")
    if result.ok:
        print(result.title, len(result.text))
        print(result.as_markdown())

The function never raises for ordinary "the web is messy" failures - it
returns a :class:`FetchResult` with ``ok=False`` and a readable ``error``,
which is what you want when a model is driving the call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from . import _http
from .html2text import html_to_text

__all__ = ["FetchResult", "fetch_url"]

_HTML_TYPES = {"text/html", "application/xhtml+xml"}
_TEXT_TYPES = {
    "application/json", "application/xml", "application/javascript",
    "application/ld+json", "application/rss+xml", "application/atom+xml",
    "application/yaml", "application/x-yaml", "application/toml",
}


@dataclass
class FetchResult:
    """Everything an agent needs to know about one fetch."""

    url: str
    ok: bool
    status: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    title: str | None = None
    text: str = ""
    truncated: bool = False
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "ok": self.ok,
            "status": self.status,
            "final_url": self.final_url,
            "content_type": self.content_type,
            "title": self.title,
            "text": self.text,
            "truncated": self.truncated,
            "error": self.error,
            **({"meta": self.meta} if self.meta else {}),
        }

    def as_markdown(self) -> str:
        """Render the result as a self-describing Markdown block."""
        if not self.ok:
            return f"**Fetch failed:** {self.error}"
        lines = []
        if self.title:
            lines.append(f"# {self.title}")
            lines.append("")
        lines.append(f"Source: {self.final_url or self.url}")
        lines.append("")
        lines.append(self.text)
        return "\n".join(lines)

    def __bool__(self) -> bool:
        return self.ok


def _pretty_json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return text


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    head = text[:max_chars].rstrip()
    removed = len(text) - len(head)
    return f"{head}\n\n[... truncated {removed:,} characters ...]", True


def fetch_url(
    url: str,
    *,
    max_chars: int = 20_000,
    timeout: float = _http.DEFAULT_TIMEOUT,
    max_bytes: int = _http.DEFAULT_MAX_BYTES,
    raw_html: bool = False,
    allow_private: bool = False,
    extra_headers: dict[str, str] | None = None,
    user_agent: str = _http.DEFAULT_USER_AGENT,
) -> FetchResult:
    """Fetch ``url`` and return it as readable text.

    Args:
        url: Absolute ``http(s)`` URL.
        max_chars: Cap on returned characters (the rest is replaced by a
            truncation marker). Set to ``0`` for no cap.
        timeout: Socket timeout in seconds.
        max_bytes: Cap on bytes read from the network.
        raw_html: Skip HTML-to-text conversion and return the markup.
        allow_private: Permit loopback / private targets. Off by default so
            an LLM cannot be tricked into reading internal endpoints.
        extra_headers: Additional request headers.
        user_agent: Override the default User-Agent.
    """
    if max_chars < 0:
        raise ValueError("max_chars must be >= 0")

    result = FetchResult(url=url, ok=False)

    try:
        resp = _http.request(
            url,
            timeout=timeout,
            max_bytes=max_bytes,
            allow_private=allow_private,
            headers=extra_headers,
            user_agent=user_agent,
        )
    except _http.HttpStatusError as exc:
        result.status = exc.status
        result.error = f"HTTP {exc.status}"
        if exc.body:
            snippet = exc.body[:400].decode("utf-8", "replace").strip()
            if snippet:
                result.error = f"HTTP {exc.status}: {snippet}"
        return result
    except _http.WebToolError as exc:
        result.error = str(exc)
        return result

    result.status = resp.status
    result.final_url = resp.url
    result.content_type = resp.content_type or None

    ctype = resp.content_type
    if not ctype:
        ctype = "text/plain"

    try:
        if ctype in _HTML_TYPES or ctype.endswith("+html"):
            body = resp.text()
            if raw_html:
                text, result.title = body, None
            else:
                doc = html_to_text(body)
                text, result.title = doc.text, doc.title
        elif ctype in _TEXT_TYPES or ctype.endswith(("+json", "+xml")):
            body = resp.text()
            text = _pretty_json(body) if (ctype.endswith("json")) else body
        elif ctype.startswith("text/"):
            text = resp.text()
        else:
            result.error = (
                f"Unsupported content type {ctype!r}. "
                "Use the search tool or a different URL for binary content."
            )
            return result
    except Exception as exc:  # pragma: no cover - defensive
        result.error = f"Could not decode response: {exc}"
        return result

    if max_chars:
        text, truncated = _truncate(text, max_chars)
        result.truncated = result.truncated or truncated
    result.truncated = result.truncated or resp.truncated
    result.text = text
    result.ok = True
    if resp.truncated:
        result.meta["byte_limit_reached"] = max_bytes
    return result
