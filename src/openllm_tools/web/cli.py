"""Command line interface: ``python -m openllm_tools.web ...`` or ``openllm-web``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Sequence

from .brave import ENV_VAR, BraveAPIError, brave_search
from .fetch import fetch_url
from .schemas import as_anthropic_tools, as_openai_tools, tool_names

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def _print_json(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _cmd_fetch(args: argparse.Namespace) -> int:
    result = fetch_url(
        args.url,
        max_chars=args.max_chars,
        timeout=args.timeout,
        raw_html=args.raw_html,
        allow_private=args.allow_private,
    )
    if args.json:
        _print_json(
            {
                **result.to_dict(),
                "text": "" if args.no_text else result.text,
            }
        )
    else:
        if not result.ok:
            print(f"error: {result.error}", file=sys.stderr)
            return EXIT_ERROR
        print(result.as_markdown())
        if result.truncated:
            print("\n[output truncated]", file=sys.stderr)
    return EXIT_OK if result.ok else EXIT_ERROR


def _cmd_search(args: argparse.Namespace) -> int:
    try:
        response = brave_search(
            args.query,
            count=args.count,
            offset=args.offset,
            country=args.country,
            freshness=args.freshness,
            safesearch=args.safesearch,
            extra_snippets=args.extra_snippets,
            timeout=args.timeout,
        )
    except BraveAPIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        _print_json({"ok": True, **response.to_dict()})
    else:
        print(response.as_markdown())
    return EXIT_OK


def _cmd_tools(args: argparse.Namespace) -> int:
    if args.format == "openai":
        _print_json({"tools": as_openai_tools()})
    elif args.format == "anthropic":
        _print_json({"tools": as_anthropic_tools()})
    else:
        _print_json({"tools": [{"name": n} for n in tool_names()]})
    return EXIT_OK


def _cmd_doctor(_args: argparse.Namespace) -> int:
    key = os.environ.get(ENV_VAR, "").strip()
    masked = f"{key[:6]}...{key[-4:]}" if len(key) > 12 else ("set" if key else "missing")
    print("openllm_tools.web")
    print(f"  python          : {sys.version.split()[0]}")
    print(f"  {ENV_VAR:<15}: {masked}")
    print(f"  tools           : {', '.join(tool_names())}")
    print("  network         : ready (stdlib urllib)")
    return EXIT_OK if key else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openllm-web",
        description="Fetch web pages and run Brave searches from the command line.",
    )
    parser.add_argument("-V", "--version", action="version", version="openllm-tools 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch a URL and print it as text/Markdown")
    fetch.add_argument("url", help="Absolute http(s) URL")
    fetch.add_argument("--max-chars", type=int, default=20000,
                       help="Maximum characters to return (default: 20000, 0 = no limit)")
    fetch.add_argument("--timeout", type=float, default=20.0, help="Timeout in seconds")
    fetch.add_argument("--raw-html", action="store_true", help="Return raw HTML")
    fetch.add_argument("--allow-private", action="store_true",
                       help="Allow loopback/private addresses (disabled for safety)")
    fetch.add_argument("--json", action="store_true", help="Emit JSON")
    fetch.add_argument("--no-text", action="store_true",
                       help="With --json, omit the body text")
    fetch.set_defaults(func=_cmd_fetch)

    search = sub.add_parser("search", help="Search the web with the Brave API")
    search.add_argument("query", help="Search terms")
    search.add_argument("-n", "--count", type=int, default=5, help="Results (1-20)")
    search.add_argument("--offset", type=int, default=0, help="Page offset (0-9)")
    search.add_argument("--country", help="Two-letter country code, e.g. US")
    search.add_argument("--freshness", help="pd, pw, pm, py or YYYY-MM-DDtoYYYY-MM-DD")
    search.add_argument("--safesearch", default="moderate",
                        choices=["off", "moderate", "strict"])
    search.add_argument("--extra-snippets", action="store_true",
                        help="Include extra excerpts per result")
    search.add_argument("--timeout", type=float, default=20.0)
    search.add_argument("--json", action="store_true", help="Emit JSON")
    search.set_defaults(func=_cmd_search)

    tools = sub.add_parser("tools", help="Print tool schemas for an LLM")
    tools.add_argument("--format", choices=["names", "openai", "anthropic"], default="names")
    tools.set_defaults(func=_cmd_tools)

    doctor = sub.add_parser("doctor", help="Show environment / configuration status")
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:  # pragma: no cover - e.g. `| head`
        return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
