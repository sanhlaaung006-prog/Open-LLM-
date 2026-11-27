# Open-LLM — Android app

A single native Android app that wraps the consumer AI chat sites (ChatGPT, Claude, Gemini, Grok, Perplexity, Copilot, DeepSeek, Qwen, Kimi, Meta AI, Le Chat, Poe, You.com) and can throw **one prompt at several of them at once** — the thing people do manually with ten browser tabs.

Kotlin + Jetpack Compose, one activity, one WebView per site.

---

## Get the APK

**Direct download (v0.1.0):**
[`app-debug.apk`](https://github.com/sanhlaaung006-prog/Open-LLM-/releases/download/v0.1.0/app-debug.apk) — 8.8 MB.

Open that link on the phone, allow "install unknown apps" when Android asks, and
install. It is a **debug build** (package `ai.openllm.launcher.debug`), so it can
sit next to a future release build.

Prefer building it yourself?

- **CI:** Actions → **android-apk** → newest green run → download the
  `OpenLLM-debug-apk` artifact (a zip containing `app-debug.apk`).
- **Locally:** see below.

Tagging a release attaches a fresh APK build to it:

```bash
git tag v0.1.1 && git push origin v0.1.1
```

### Build it yourself

```bash
cd android
gradle :app:assembleDebug          # or open the folder in Android Studio
adb install app/build/outputs/apk/debug/app-debug.apk
```

Needs JDK 17 and Android SDK 34. There is deliberately no Gradle wrapper jar in
this repo, so CI calls a pinned Gradle (`8.7`) directly; if you prefer a wrapper
run `gradle wrapper` once locally.

---

## What it does

### Tabs, one per site

Every site you open gets its own `WebView` that stays alive while you switch, so
a reply that is still streaming is not thrown away, and every site keeps its own
logged-in session (cookies persist across launches).

### Ask every model (`Ask every model` button)

Type once, pick the sites, send:

- Sites with a **prefill URL** open with the question already in the chat
  (ChatGPT, Claude, Grok, Perplexity, Copilot, You.com).
- Sites without one get a **Paste** banner: one tap types the prompt into the
  page's own composer using its input events, so React/Lexical/ProseMirror
  editors accept it.

Tabs carrying a queued prompt show a small dot.

### Share into the app

The app registers for `ACTION_SEND` and `ACTION_PROCESS_TEXT`, so text shared
from any app — or highlighted and sent via the text-selection menu — opens the
composer pre-filled.

### Model manager

Enable/disable, reorder, add your own chat URL, or reset to the shipped list.
Stored locally in `SharedPreferences` as JSON; shipped providers are merged by
id so app updates can fix URLs without wiping your settings.

### The rest

- File uploads (attachment button in any chat) via the system picker
- Downloads go through `DownloadManager` with the site's cookies
- Microphone permission for voice input (camera requests are declined)
- System dark mode: the app theme plus the sites' own dark rendering
- Back button walks the page history, then leaves the app

---

## Provider prefill support

| Site | Prefill | URL used |
| --- | --- | --- |
| ChatGPT | yes | `chatgpt.com/?q=` |
| Claude | yes | `claude.ai/new?q=` |
| Grok | yes | `grok.com/?q=` |
| Perplexity | yes | `perplexity.ai/search?q=` |
| Copilot | yes | `copilot.microsoft.com/?q=` |
| You.com | yes | `you.com/search?q=` |
| Gemini, DeepSeek, Qwen, Kimi, Meta AI, Le Chat, Poe | no → Paste banner | home page |

Prefill URLs are best-effort: those are the sites' own "start a chat with this
question" links. If one changes, the tab opens at the home page and the Paste
button handles it — nothing breaks, and you can edit the URL in
`data/ProviderCatalog.kt`.

## Known limitations

- **Google sign-in.** Google refuses OAuth inside embedded browsers
  (`403 disallowed_useragent`), which affects signing into Gemini with a Google
  account. Workarounds: sign in on the site in Chrome first (cookies are not
  shared), or use the site's own email login where offered. Setting
  `UserAgentMode.CHROME_LIKE` on a provider strips the `wv` marker, which helps
  some sites but does not satisfy Google's OAuth policy.
- **No push notifications.** These are websites; nothing runs in the background.
  Replies keep streaming while the tab is alive, not after you leave the app.
- **Memory.** Each visited site is a live WebView. Visits to many heavy sites at
  once will be reclaimed by Android on low-memory devices — those tabs reload.
- **Site updates.** These are third-party UIs; a redesign can change a selector
  or an inline script. The app degrades to a plain browser tab when that happens.
- **Not store-ready.** Releases are signed with the debug key so they install
  anywhere. Replace `signingConfig` before distributing on Play.

## Layout

```
app/src/main/java/ai/openllm/launcher/
  MainActivity.kt          # edge-to-edge host, file picker, mic, share intents
  AppViewModel.kt          # provider list, active tab, queued prompts
  data/Provider.kt         # one wrapped site + its prefill template
  data/ProviderCatalog.kt  # the 13 shipped sites
  data/ProviderStore.kt    # SharedPreferences JSON persistence
  web/WebViewPool.kt       # session-preserving WebViews, downloads, JS paste
  ui/AppRoot.kt            # header, tab strip, banner, ask bar
  ui/ComposerSheet.kt      # "ask every model" composer
  ui/SettingsSheet.kt      # model manager + add-site dialog
  ui/Theme.kt              # Material 3 theme
```

## Privacy

The app has no analytics, no backend and no accounts of its own. It talks only
to the sites you open, using their normal web sessions. Nothing leaves the
device except the requests those sites already receive.
