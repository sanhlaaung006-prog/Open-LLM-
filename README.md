# Open-LLM-

LLM tooling that runs on a bare Python install.

The first module is **`openllm_tools.web`** — a web-fetch tool and a [Brave Search](https://brave.com/search/api/) tool, packaged so an agent can call them and a human can use them from the terminal.

- **Zero dependencies** — standard library only (`urllib`, `html.parser`, `json`)
- **Agent-ready** — OpenAI and Anthropic tool schemas included, plus a dispatcher
- **Readable output** — HTML is converted to compact Markdown instead of raw markup
- **Safe by default** — refuses loopback/private addresses (SSRF guard), byte and character caps
- **Tested** — 57 tests, no network required to run them

---

## Install

```bash
git clone https://github.com/sanhlaaung006-prog/Open-LLM-.git
cd Open-LLM-
python3 -m pip install -e .
```

No dependencies are pulled in. If you would rather not install anything:

```bash
PYTHONPATH=src python3 -m openllm_tools.web fetch https://example.com
```

Requires Python 3.10+.

## Brave search key

The fetch tool needs no credentials. Brave Search needs a free/paid API key:

```bash
export BRAVE_API_KEY=BSA...      # https://api.search.brave.com/app/keys
```

Check everything is wired up:

```bash
$ openllm-web doctor
openllm_tools.web
  python          : 3.11.2
  BRAVE_API_KEY   : BSAabc...wxyz
  tools           : web_fetch, web_search
  network         : ready (stdlib urllib)
```

---

## Command line

```bash
# Read a page as Markdown
openllm-web fetch https://example.com

# Read a page as JSON, capped at 4k characters
openllm-web fetch https://example.com --max-chars 4000 --json

# Search the web (recency-filtered, US)
openllm-web search "open source LLM inference" --count 5 --freshness pw --country US

# Print tool schemas to paste into a prompt or SDK
openllm-web tools --format openai
openllm-web tools --format anthropic
```

`fetch --json` returns:

```json
{
  "url": "https://example.com",
  "ok": true,
  "status": 200,
  "final_url": "https://example.com/",
  "content_type": "text/html",
  "title": "Example Domain",
  "text": "# Example Domain\n\nThis domain is for use in illustrative examples...",
  "truncated": false,
  "error": null
}
```

Exit codes: `0` success, `1` fetch/search failure, `2` bad usage.

## Python

```python
from openllm_tools.web import fetch_url, brave_search

page = fetch_url("https://example.com", max_chars=8000)
if page.ok:
    print(page.title)          # "Example Domain"
    print(page.text)           # Markdown-ish body
    print(page.as_markdown())  # title + source + body
else:
    print(page.error)          # "HTTP 404: ..." / "Could not resolve host ..."

hits = brave_search("python asyncio tutorial", count=5, freshness="py")
for r in hits.results:
    print(r.title, "->", r.url)

print(hits.as_markdown())
```

Both entry points return data instead of raising for ordinary failures, so a model can read the error and retry.

### `fetch_url()`

| Argument | Default | Meaning |
| --- | --- | --- |
| `max_chars` | `20000` | Character cap for returned text (`0` = no cap) |
| `timeout` | `20.0` | Socket timeout in seconds |
| `max_bytes` | `5 MiB` | Bytes read from the network |
| `raw_html` | `False` | Return markup instead of cleaned text |
| `allow_private` | `False` | Permit loopback/private targets |
| `extra_headers` | `None` | Extra request headers |
| `user_agent` | `openllm-tools/0.1` | Override the User-Agent |

### `brave_search()`

| Argument | Default | Meaning |
| --- | --- | --- |
| `count` | `5` | Results per page (1–20) |
| `offset` | `0` | Page offset (0–9) |
| `country` | `None` | Two-letter code, e.g. `US` |
| `search_lang` | `None` | Language code, e.g. `en` |
| `freshness` | `None` | `pd` / `pw` / `pm` / `py`, or `YYYY-MM-DDtoYYYY-MM-DD` |
| `safesearch` | `moderate` | `off` / `moderate` / `strict` |
| `extra_snippets` | `False` | Up to five extra excerpts per result |
| `api_key` | env | Overrides `BRAVE_API_KEY` |

Errors map to typed exceptions: `BraveAuthError` (missing/rejected key), `BraveRateLimitError` (429), `BraveQueryError` (bad parameters), `BraveAPIError` (anything else).

## Plugging into an LLM

```python
from openllm_tools.web.schemas import as_openai_tools, dispatch

tools = as_openai_tools()                 # -> tools=[...] for chat completions
result = dispatch("web_fetch", {"url": "https://example.com"})   # -> dict
```

`as_anthropic_tools()` returns the same two tools as `{"name", "description", "input_schema"}`.
`dispatch()` never raises: unknown tools, missing arguments and API errors all come back as `{"ok": False, "error": "..."}` so the agent loop can recover.

`examples/agent_loop.py` shows the complete loop — search, read the top hit, summarise — and runs offline with a scripted model:

```bash
python3 examples/agent_loop.py
OPENAI_API_KEY=sk-... python3 examples/agent_loop.py "who maintains pytest?"
```

---

## Safety notes

- **SSRF guard.** Hostnames are resolved and any non-public address (loopback, RFC1918, link-local/cloud metadata, CGNAT, reserved) is refused unless `allow_private=True`. Resolve-then-connect has an inherent TOCTOU gap; for untrusted URLs in production, put the fetcher behind an egress proxy.
- **Resource caps.** `max_bytes` bounds memory, `max_chars` bounds prompt size.
- **No JS execution.** Pages that render client-side will look empty. That is a deliberate trade for having no browser dependency.

## Layout

```
src/openllm_tools/web/
  _http.py       # stdlib HTTP client: gzip, caps, SSRF guard
  html2text.py   # HTML -> Markdown-ish text
  fetch.py       # fetch_url() -> FetchResult
  brave.py       # brave_search() -> SearchResponse
  schemas.py     # OpenAI/Anthropic tool schemas + dispatch()
  cli.py         # openllm-web
tests/           # unittest suite against a local HTTP server
examples/agent_loop.py
```

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -t tests   # no network needed
python3 -m pip install pytest && pytest                          # or via pytest
```

## License

MIT
