# Open-LLM-

**Consumer frontier AI chatbots in one place** — plus the small web toolkit that
powers it.

| Part | What it is |
| --- | --- |
| [`android/`](android/) | **Native Android app (APK)**: wraps 13 consumer AI chat sites in one shell and lets you fire a single prompt at several models at once. Kotlin + Jetpack Compose. |
| `src/openllm_tools/` | Dependency-free Python web tools (page fetching + Brave Search) with OpenAI/Anthropic tool schemas, used by the app's research flow and scriptable on its own. |

---

## The app

One prompt → every model you selected. Tabs keep their sessions and their
in-flight replies, so you can compare ChatGPT, Claude, Gemini, Grok, Perplexity,
Copilot, DeepSeek, Qwen, Kimi, Meta AI, Le Chat, Poe and You.com side by side.

**Get the APK:** [download `app-debug.apk` (v0.1.0)](https://github.com/sanhlaaung006-prog/Open-LLM-/releases/download/v0.1.0/app-debug.apk)
— or grab it from Actions → *android-apk* → newest run. Details, provider table
and known limitations live in [`android/README.md`](android/README.md).

<table>
<tr><td width="50%">

**Ask every model**

Type once, tick the sites, send. Sites with a prefill URL open with the question
already sent; the rest get a one-tap **Paste** that types into their own
composer.

</td><td width="50%">

**One place, real sessions**

Each site keeps its login and stays alive while you switch tabs, so a streaming
answer is never lost. Share text into the app from anywhere.

</td></tr>
</table>

Built with Kotlin, Jetpack Compose, Material 3, and a lot of respect for how
fragile third-party web UIs are (every fallback is graceful: no prefill → Paste
banner; no chat box → clipboard).

---

## The web tools (`openllm_tools.web`)

Standard-library-only Python. No dependencies to install, no SDK to configure.

- **`fetch_url()`** — stdlib HTTP with gzip, redirects, byte/char caps and an
  SSRF guard; HTML is converted to compact Markdown for a model to read.
- **`brave_search()`** — typed client for the [Brave Search API](https://brave.com/search/api/)
  (auth, rate-limit and query errors are distinct exceptions).
- **Tool schemas** — the same two tools exported for OpenAI and Anthropic
  function calling, with a `dispatch()` that never raises.
- **`openllm-web` CLI** — `fetch`, `search`, `tools`, `doctor`.

```bash
python3 -m pip install -e .
export BRAVE_API_KEY=BSA...     # https://api.search.brave.com/app/keys
openllm-web doctor
openllm-web fetch https://example.com --max-chars 4000
openllm-web search "open source LLM inference" --count 5 --freshness pw
openllm-web tools --format openai
```

### Python API

```python
from openllm_tools.web import fetch_url, brave_search

page = fetch_url("https://example.com", max_chars=8000)
if page.ok:
    print(page.title, page.text[:200])

for hit in brave_search("python asyncio tutorial", count=3).results:
    print(hit.title, "->", hit.url)
```

### Plugging into an LLM

```python
from openllm_tools.web.schemas import as_openai_tools, dispatch

tools = as_openai_tools()                                   # tools=[...] for chat completions
result = dispatch("web_fetch", {"url": "https://example.com"})   # -> dict, never raises
```

`examples/agent_loop.py` shows the whole search → read → answer loop and runs
offline with a scripted model.

---

## Repository layout

```
android/                  Native app (see android/README.md)
  app/src/main/java/ai/openllm/launcher/
  app/src/main/AndroidManifest.xml
.github/workflows/
  android.yml             Builds the APK and publishes it as an artifact/release
  tests.yml               Python test suite (3.10 / 3.11 / 3.12)
src/openllm_tools/web/    _http.py, html2text.py, fetch.py, brave.py, schemas.py, cli.py
tests/                    unittest suite against a local HTTP server (no network)
examples/agent_loop.py
```

## Development

```bash
# Python tools
PYTHONPATH=src python3 -m unittest discover -s tests -t tests

# Android app
cd android && gradle :app:assembleDebug
```

## License

MIT
