"""A minimal tool-calling loop built on the web tools.

The point of this file is to show the wiring, not to be a framework:

1. describe the tools to the model (:func:`as_openai_tools`)
2. let the model answer with a tool call
3. run it with :func:`dispatch`
4. feed the JSON result back in

Run it offline (a scripted "model" stands in for a real one)::

    python examples/agent_loop.py

Run it against a real model by setting ``OPENAI_API_KEY`` (any
OpenAI-compatible endpoint works - swap ``OPENAI_BASE_URL``)::

    OPENAI_API_KEY=sk-... python examples/agent_loop.py "who maintains pytest?"
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from openllm_tools.web.schemas import as_openai_tools, dispatch  # noqa: E402

SYSTEM = (
    "You are a research assistant. Use web_search to find sources and web_fetch "
    "to read them. Cite URLs in your final answer."
)


def scripted_model(messages: list[dict]) -> dict:
    """A fake model: search once, fetch the first hit, then summarise."""
    tool_turns = [m for m in messages if m["role"] == "tool"]
    if not tool_turns:
        return _tool_call("web_search", {"query": "python asyncio tutorial", "count": 2})
    if len(tool_turns) == 1:
        payload = json.loads(tool_turns[0]["content"])
        url = payload.get("results", [{}])[0].get("url")
        if url:
            return _tool_call("web_fetch", {"url": url, "max_chars": 3000})
    last = json.loads(tool_turns[-1]["content"])
    excerpt = (last.get("text") or last.get("error") or "")[:300].replace("\n", " ")
    return {
        "role": "assistant",
        "content": f"(demo) Here is the gist: {excerpt}...",
    }


def _tool_call(name: str, arguments: dict) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{name}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def openai_model(messages: list[dict]) -> dict:
    """Call an OpenAI-compatible /chat/completions endpoint."""
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM}, *messages],
            "tools": as_openai_tools(),
            "tool_choice": "auto",
        }
    ).encode()

    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read())
    return payload["choices"][0]["message"]


def run(question: str, model, max_steps: int = 6) -> str:
    messages: list[dict] = [{"role": "user", "content": question}]
    for _ in range(max_steps):
        reply = model(messages)
        messages.append({k: v for k, v in reply.items() if v is not None})

        calls = reply.get("tool_calls") or []
        if not calls:
            return reply.get("content") or ""

        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"].get("arguments") or "{}")
            print(f"  -> {name}({json.dumps(args)[:120]})", file=sys.stderr)
            result = dispatch(name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": json.dumps(result)[:20_000],
                }
            )
    return "(stopped: step limit reached)"


def main() -> int:
    question = " ".join(sys.argv[1:]).strip() or "How do I get started with asyncio?"
    model = openai_model if os.environ.get("OPENAI_API_KEY") else scripted_model
    if model is scripted_model and not os.environ.get("BRAVE_API_KEY"):
        print(
            "No OPENAI_API_KEY or BRAVE_API_KEY set - the demo will show the "
            "tool loop but the search step will report a missing key.\n",
            file=sys.stderr,
        )
    print(run(question, model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
