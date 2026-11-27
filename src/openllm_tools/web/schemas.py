"""Tool definitions, ready to hand to an LLM.

The same two tools are exported in the shapes the common APIs expect::

    from openllm_tools.web.schemas import as_openai_tools, as_anthropic_tools

    tools = as_openai_tools()        # OpenAI / compatible chat completions
    tools = as_anthropic_tools()     # Anthropic messages API

and a dispatcher that turns a model's tool call into a JSON-able result::

    from openllm_tools.web.schemas import dispatch

    result = dispatch("web_fetch", {"url": "https://example.com"})
"""

from __future__ import annotations

import copy
from typing import Any, Callable

from .brave import BraveAPIError, brave_search
from .fetch import fetch_url

__all__ = [
    "TOOL_SCHEMAS",
    "as_anthropic_tools",
    "as_openai_tools",
    "dispatch",
    "tool_names",
]

_FETCH_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "Absolute http(s) URL of the page to read.",
        },
        "max_chars": {
            "type": "integer",
            "description": "Maximum characters of extracted text to return.",
            "default": 20000,
            "minimum": 0,
        },
        "raw_html": {
            "type": "boolean",
            "description": "Return raw HTML instead of cleaned text.",
            "default": False,
        },
    },
    "required": ["url"],
}

_SEARCH_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search terms. Supports Brave operators like site: and -word.",
        },
        "count": {
            "type": "integer",
            "description": "Number of results (1-20).",
            "default": 5,
            "minimum": 1,
            "maximum": 20,
        },
        "freshness": {
            "type": "string",
            "description": "Recency filter: pd (day), pw (week), pm (month), "
                           "py (year) or YYYY-MM-DDtoYYYY-MM-DD.",
        },
        "country": {
            "type": "string",
            "description": "Two-letter country code, e.g. US, GB, MM.",
        },
        "safesearch": {
            "type": "string",
            "enum": ["off", "moderate", "strict"],
            "default": "moderate",
        },
    },
    "required": ["query"],
}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "web_fetch",
        "description": (
            "Fetch a web page and return its readable text (HTML is converted "
            "to Markdown). Use after web_search to read a promising result, or "
            "when you already have a URL."
        ),
        "parameters": _FETCH_PARAMS,
    },
    {
        "name": "web_search",
        "description": (
            "Search the public web with the Brave Search API. Returns titles, "
            "URLs and snippets, newest first when freshness is set."
        ),
        "parameters": _SEARCH_PARAMS,
    },
]


def tool_names() -> list[str]:
    return [tool["name"] for tool in TOOL_SCHEMAS]


def as_openai_tools() -> list[dict[str, Any]]:
    """Tool list in OpenAI ``tools=[{"type": "function", ...}]`` format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": copy.deepcopy(tool["parameters"]),
            },
        }
        for tool in TOOL_SCHEMAS
    ]


def as_anthropic_tools() -> list[dict[str, Any]]:
    """Tool list in Anthropic ``tools=[{"name": ..., "input_schema": ...}]`` format."""
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": copy.deepcopy(tool["parameters"]),
        }
        for tool in TOOL_SCHEMAS
    ]


def _pick(arguments: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    ignored = set(arguments) - allowed
    return {k: v for k, v in arguments.items() if k in allowed}


def _run_fetch(arguments: dict[str, Any]) -> dict[str, Any]:
    url = arguments.get("url")
    if not isinstance(url, str) or not url.strip():
        return {"ok": False, "error": "web_fetch requires a non-empty 'url'"}
    kwargs = _pick(arguments, {"max_chars", "raw_html"})
    result = fetch_url(url.strip(), **kwargs)
    return result.to_dict()


def _run_search(arguments: dict[str, Any]) -> dict[str, Any]:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"ok": False, "error": "web_search requires a non-empty 'query'"}
    kwargs = _pick(
        arguments, {"count", "offset", "country", "search_lang", "freshness", "safesearch"}
    )
    try:
        response = brave_search(query, **kwargs)
    except BraveAPIError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **response.to_dict()}


_DISPATCH: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "web_fetch": _run_fetch,
    "web_search": _run_search,
}


def dispatch(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a tool call and return a JSON-serialisable result.

    Unknown tool names and bad arguments come back as ``{"ok": False, ...}``
    rather than raising, so a model can read the error and retry.
    """
    handler = _DISPATCH.get(name)
    if handler is None:
        return {
            "ok": False,
            "error": f"Unknown tool {name!r}. Available: {', '.join(tool_names())}",
        }
    try:
        return handler(arguments or {})
    except TypeError as exc:
        return {"ok": False, "error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:  # keep the agent loop alive
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
