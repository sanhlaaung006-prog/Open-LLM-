"""Brave Search API client (``/res/v1/web/search``).

Docs: https://api.search.brave.com/app/documentation/web-search/get-started

Get a key at https://api.search.brave.com/app/keys and export it::

    export BRAVE_API_KEY=BSA...

Then::

    from openllm_tools.web import brave_search

    hits = brave_search("open source LLM inference", count=5)
    for hit in hits.results:
        print(hit.title, hit.url)

The client is stdlib-only and takes an injectable ``transport`` so the
whole thing can be tested without network access.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable

from . import _http

__all__ = [
    "BRAVE_ENDPOINT",
    "ENV_VAR",
    "BraveAPIError",
    "BraveAuthError",
    "BraveQueryError",
    "BraveRateLimitError",
    "SearchResponse",
    "SearchResult",
    "brave_search",
]

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
ENV_VAR = "BRAVE_API_KEY"

MAX_COUNT = 20
MAX_OFFSET = 9
FRESHNESS_VALUES = {"pd", "pw", "pm", "py"}
SAFESEARCH_VALUES = {"off", "moderate", "strict"}

# transport(url, headers, timeout) -> (status, headers, body)
Transport = Callable[[str, dict[str, str], float], "tuple[int, dict[str, str], bytes]"]


class BraveAPIError(RuntimeError):
    """Base class for Brave Search errors."""


class BraveAuthError(BraveAPIError):
    """Missing key, or the key was rejected (401/403)."""


class BraveRateLimitError(BraveAPIError):
    """Too many requests (429)."""


class BraveQueryError(BraveAPIError):
    """The request itself was invalid (4xx other than auth/429)."""


@dataclass
class SearchResult:
    title: str
    url: str
    description: str = ""
    age: str | None = None
    source: str | None = None
    extra_snippets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "title": self.title,
            "url": self.url,
            "description": self.description,
        }
        if self.age:
            data["age"] = self.age
        if self.source:
            data["source"] = self.source
        if self.extra_snippets:
            data["extra_snippets"] = self.extra_snippets
        return data

    def as_markdown(self, index: int) -> str:
        line = f"{index}. [{self.title}]({self.url})"
        if self.source:
            line += f" - *{self.source}*"
        if self.age:
            line += f" ({self.age})"
        if self.description:
            line += f"\n   {self.description}"
        return line


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    infobox: dict[str, Any] | None = None
    faq: list[dict[str, Any]] = field(default_factory=list)
    news: list[SearchResult] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
        }
        if self.infobox:
            data["infobox"] = self.infobox
        if self.faq:
            data["faq"] = self.faq
        if self.news:
            data["news"] = [n.to_dict() for n in self.news]
        return data

    def as_markdown(self) -> str:
        if not self.results:
            return f"No results for {self.query!r}."
        lines = [f"## Search results for {self.query!r}", ""]
        lines += [r.as_markdown(i) for i, r in enumerate(self.results, 1)]
        if self.news:
            lines += ["", "### News", ""]
            lines += [f"- [{n.title}]({n.url})" for n in self.news]
        return "\n".join(lines)


def _default_transport(url: str, headers: dict[str, str], timeout: float):
    resp = _http.request(url, headers=headers, timeout=timeout, max_bytes=8 * 1024 * 1024)
    return resp.status, resp.headers, resp.body


def _clean(text: Any) -> str:
    """Brave returns light HTML tags (<strong>) in descriptions."""
    if not isinstance(text, str):
        return ""
    out = text.replace("<strong>", "").replace("</strong>", "")
    out = out.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
    return " ".join(out.split())


def _to_result(item: dict[str, Any]) -> SearchResult:
    profile = item.get("profile") or {}
    return SearchResult(
        title=_clean(item.get("title")) or "(untitled)",
        url=item.get("url", ""),
        description=_clean(item.get("description")),
        age=item.get("age") or None,
        source=_clean(profile.get("name")) or None,
        extra_snippets=[_clean(s) for s in item.get("extra_snippets") or [] if s],
    )


def _build_url(
    query: str,
    count: int,
    offset: int,
    country: str | None,
    search_lang: str | None,
    freshness: str | None,
    safesearch: str,
    extra_snippets: bool,
    spellcheck: bool,
) -> str:
    params: dict[str, str] = {
        "q": query,
        "count": str(count),
        "offset": str(offset),
        "safesearch": safesearch,
        "text_decorations": "0",
        "spellcheck": "1" if spellcheck else "0",
    }
    if extra_snippets:
        params["extra_snippets"] = "1"
    if country:
        params["country"] = country.upper()
    if search_lang:
        params["search_lang"] = search_lang
    if freshness:
        params["freshness"] = freshness
    return f"{BRAVE_ENDPOINT}?{urllib.parse.urlencode(params)}"


def brave_search(
    query: str,
    *,
    count: int = 5,
    offset: int = 0,
    country: str | None = None,
    search_lang: str | None = None,
    freshness: str | None = None,
    safesearch: str = "moderate",
    extra_snippets: bool = False,
    spellcheck: bool = True,
    api_key: str | None = None,
    timeout: float = 20.0,
    transport: Transport | None = None,
) -> SearchResponse:
    """Run a Brave web search.

    Args:
        query: Search terms (1-400 characters).
        count: Results to return, 1-20.
        offset: Page offset, 0-9.
        country: Two-letter country code, e.g. ``"US"``.
        search_lang: Language code, e.g. ``"en"``.
        freshness: ``"pd"`` (day), ``"pw"`` (week), ``"pm"`` (month),
            ``"py"`` (year), or an explicit ``YYYY-MM-DDtoYYYY-MM-DD`` range.
        safesearch: ``"off"``, ``"moderate"`` or ``"strict"``.
        extra_snippets: Ask for up to five extra excerpts per result.
        spellcheck: Let Brave fix typos in the query.
        api_key: Overrides ``BRAVE_API_KEY``.
        timeout: Request timeout in seconds.
        transport: Injectable HTTP function (used by the test-suite).

    Raises:
        BraveAuthError: No key configured, or the key was rejected.
        BraveRateLimitError: The plan's rate limit was hit.
        BraveQueryError: Brave rejected the request parameters.
        BraveAPIError: Any other API or network failure.
    """
    query = " ".join((query or "").split())
    if not query:
        raise BraveQueryError("Search query must not be empty")
    if len(query) > 400:
        raise BraveQueryError("Search query must be 400 characters or fewer")
    if not 1 <= count <= MAX_COUNT:
        raise BraveQueryError(f"count must be between 1 and {MAX_COUNT}")
    if not 0 <= offset <= MAX_OFFSET:
        raise BraveQueryError(f"offset must be between 0 and {MAX_OFFSET}")
    if safesearch not in SAFESEARCH_VALUES:
        raise BraveQueryError(f"safesearch must be one of {sorted(SAFESEARCH_VALUES)}")
    if freshness and freshness not in FRESHNESS_VALUES and "to" not in freshness:
        raise BraveQueryError(
            "freshness must be one of pd, pw, pm, py or a YYYY-MM-DDtoYYYY-MM-DD range"
        )

    key = api_key or os.environ.get(ENV_VAR, "").strip()
    if not key:
        raise BraveAuthError(
            f"No Brave API key found. Set {ENV_VAR} or pass api_key=... "
            "Create a key at https://api.search.brave.com/app/keys"
        )

    url = _build_url(
        query, count, offset, country, search_lang, freshness, safesearch,
        extra_snippets, spellcheck,
    )
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": key,
    }

    try:
        status, _headers, body = (transport or _default_transport)(url, headers, timeout)
    except _http.WebToolError as exc:
        raise BraveAPIError(f"Brave Search request failed: {exc}") from exc

    if status == 401 or status == 403:
        raise BraveAuthError(
            f"Brave rejected the API key (HTTP {status}). Check {ENV_VAR} and your "
            "subscription at https://api.search.brave.com/app/keys"
        )
    if status == 429:
        raise BraveRateLimitError(
            "Brave Search rate limit exceeded (HTTP 429). Slow down or upgrade the plan."
        )
    if status >= 400:
        detail = body[:300].decode("utf-8", "replace").strip()
        raise BraveQueryError(f"Brave Search returned HTTP {status}: {detail}")

    try:
        payload = json.loads(body.decode("utf-8", "replace") or "{}")
    except ValueError as exc:
        raise BraveAPIError(f"Brave Search returned invalid JSON: {exc}") from exc

    web = payload.get("web") or {}
    results = [_to_result(item) for item in web.get("results", []) if item.get("url")]

    news = [
        SearchResult(
            title=_clean(item.get("title")) or "(untitled)",
            url=item.get("url", ""),
            description=_clean(item.get("description")),
            age=item.get("age") or None,
            source=_clean((item.get("meta_url") or {}).get("hostname")) or None,
        )
        for item in (payload.get("news") or {}).get("results", [])[:5]
        if item.get("url")
    ]

    infobox = None
    raw_infobox = payload.get("infobox")
    if isinstance(raw_infobox, dict) and raw_infobox.get("results"):
        first = raw_infobox["results"][0]
        infobox = {
            "title": _clean(first.get("title")),
            "description": _clean(first.get("long_desc") or first.get("description")),
            "url": (first.get("url") or ""),
        }

    faq = [
        {"question": _clean(q.get("question")), "answer": _clean(q.get("answer"))}
        for q in (payload.get("faq") or {}).get("results", [])[:5]
        if q.get("question")
    ]

    return SearchResponse(
        query=query, results=results, infobox=infobox, faq=faq, news=news, raw=payload
    )
