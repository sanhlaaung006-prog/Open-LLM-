"""Web tools for LLM agents: page fetching and Brave Search.

Quick start::

    from openllm_tools.web import fetch_url, brave_search

    page = fetch_url("https://example.com")
    print(page.title, page.text[:200])

    hits = brave_search("python stdlib http client", count=3)
    for hit in hits.results:
        print(hit.title, hit.url)

Command line::

    python -m openllm_tools.web fetch https://example.com
    python -m openllm_tools.web search "brave search api" --count 3
"""

from .brave import (
    BraveAPIError,
    BraveAuthError,
    BraveQueryError,
    BraveRateLimitError,
    SearchResponse,
    SearchResult,
    brave_search,
)
from .fetch import FetchResult, fetch_url
from .html2text import html_to_text
from .schemas import (
    TOOL_SCHEMAS,
    as_anthropic_tools,
    as_openai_tools,
    dispatch,
    tool_names,
)

__all__ = [
    "BraveAPIError",
    "BraveAuthError",
    "BraveQueryError",
    "BraveRateLimitError",
    "FetchResult",
    "SearchResponse",
    "SearchResult",
    "TOOL_SCHEMAS",
    "as_anthropic_tools",
    "as_openai_tools",
    "brave_search",
    "dispatch",
    "fetch_url",
    "html_to_text",
    "tool_names",
]
