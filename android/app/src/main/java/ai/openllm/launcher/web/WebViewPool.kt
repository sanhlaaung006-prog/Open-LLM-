package ai.openllm.launcher.web

import android.annotation.SuppressLint
import android.app.Activity
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.view.View
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.webkit.WebSettingsCompat
import androidx.webkit.WebViewFeature
import ai.openllm.launcher.data.Provider
import ai.openllm.launcher.data.UserAgentMode
import org.json.JSONObject

/**
 * Keeps one live [WebView] per provider so switching tabs never loses a reply
 * that is still streaming, and so each site keeps its own login session.
 *
 * Views are created lazily - only sites the user actually opens allocate a
 * process-level WebView.
 */
class WebViewPool(
    private val activity: Activity,
    private val onFileChooser: (WebChromeClient.FileChooserParams) -> Unit,
    private val onPermissionRequest: (PermissionRequest) -> Unit,
    private val onOpenExternal: (String) -> Unit,
    private val onMessage: (String) -> Unit,
) {

    private var container: FrameLayout? = null
    private val views = LinkedHashMap<String, WebView>()
    private val loadedPrompts = HashMap<String, String>()
    private var desired: Pair<Provider, String?>? = null
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    val currentId: String? get() = desired?.first?.id

    /** Called once by the Compose host with the container the views live in. */
    fun attach(frame: FrameLayout) {
        container = frame
        desired?.let { (provider, prompt) -> applyShow(provider, prompt) }
    }

    fun show(provider: Provider, prompt: String?) {
        desired = provider to prompt
        applyShow(provider, prompt)
    }

    private fun applyShow(provider: Provider, prompt: String?) {
        val frame = container ?: return

        val existing = views[provider.id]
        if (existing == null) {
            val created = create(provider)
            views[provider.id] = created
            frame.addView(created)
            loadedPrompts[provider.id] = prompt.orEmpty()
            created.loadUrl(provider.urlFor(prompt))
        } else if (!prompt.isNullOrBlank() && loadedPrompts[provider.id] != prompt) {
            loadedPrompts[provider.id] = prompt
            existing.loadUrl(provider.urlFor(prompt))
        }

        views.forEach { (id, candidate) ->
            candidate.visibility = if (id == provider.id) View.VISIBLE else View.GONE
        }
    }

    fun reload(providerId: String) {
        views[providerId]?.reload()
    }

    fun goBack(providerId: String?): Boolean {
        val view = providerId?.let { views[it] } ?: return false
        return if (view.canGoBack()) {
            view.goBack()
            true
        } else {
            false
        }
    }

    /** Apply the system dark-mode preference to every live page. */
    fun applyDark(enabled: Boolean) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.ALGORITHMIC_DARKENING)) return
        views.values.forEach { view ->
            runCatching {
                WebSettingsCompat.setAlgorithmicDarkeningAllowed(view.settings, enabled)
            }
        }
    }

    fun deliverFileChosen(uris: Array<Uri>?) {
        fileCallback?.onReceiveValue(uris)
        fileCallback = null
    }

    /**
     * Types [text] into the site's composer using the page's own input events.
     * Best effort: many sites use custom editors, so failures are reported
     * rather than thrown.
     */
    fun injectPrompt(providerId: String, text: String, onResult: (Boolean) -> Unit) {
        val view = views[providerId]
        if (view == null) {
            onResult(false)
            return
        }
        val script = INJECT_SCRIPT.replace("__TEXT__", JSONObject.quote(text))
        view.evaluateJavascript(script) { raw ->
            onResult(raw?.trim()?.trim('"') == "ok")
        }
    }

    fun destroy() {
        views.values.forEach { view ->
            runCatching { (view.parent as? FrameLayout)?.removeView(view) }
            runCatching { view.stopLoading() }
            runCatching { view.destroy() }
        }
        views.clear()
        container = null
        desired = null
    }

    // ---------------------------------------------------------------- setup

    @SuppressLint("SetJavaScriptEnabled")
    private fun create(provider: Provider): WebView {
        val webView = WebView(activity).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            )
            isVerticalScrollBarEnabled = true
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, true)
        }

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            builtInZoomControls = false
            displayZoomControls = false
            mediaPlaybackRequiresUserGesture = false
            javaScriptCanOpenWindowsAutomatically = true
            // Single-window mode keeps OAuth popups inside the tab instead of
            // spawning a window we would have to host ourselves.
            setSupportMultipleWindows(false)
            allowFileAccess = false
            allowContentAccess = true
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            if (provider.userAgentMode == UserAgentMode.CHROME_LIKE) {
                userAgentString = chromeLikeUserAgent(userAgentString)
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: android.webkit.WebResourceRequest,
            ): Boolean = handleUrl(view, request.url)

            @Deprecated("Deprecated in API 24, kept for old WebView builds")
            override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean =
                handleUrl(view, Uri.parse(url))
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView?,
                callback: ValueCallback<Array<Uri>>?,
                params: FileChooserParams?,
            ): Boolean {
                if (callback == null || params == null) return false
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                onFileChooser(params)
                return true
            }

            override fun onPermissionRequest(request: PermissionRequest?) {
                request ?: return
                onPermissionRequest(request)
            }
        }

        webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            if (url.startsWith("http")) enqueueDownload(url, userAgent, contentDisposition, mimeType)
            else onMessage("This file cannot be downloaded")
        }

        return webView
    }

    private fun handleUrl(view: WebView, uri: Uri): Boolean {
        return when (uri.scheme?.lowercase()) {
            "http", "https" -> false // always stay in-app
            "about", "javascript", "data", "blob" -> false
            else -> {
                // mailto:, tel:, intent:, market:, tg: ... hand off to the system
                runCatching {
                    activity.startActivity(Intent(Intent.ACTION_VIEW, uri))
                }.onFailure { onMessage("No app can open ${uri.scheme} links") }
                true
            }
        }
    }

    private fun enqueueDownload(url: String, userAgent: String?, disposition: String?, mime: String?) {
        runCatching {
            val request = DownloadManager.Request(Uri.parse(url)).apply {
                setMimeType(mime)
                addRequestHeader("User-Agent", userAgent)
                CookieManager.getInstance().getCookie(url)?.let { addRequestHeader("Cookie", it) }
                setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED,
                )
                setDestinationInExternalFilesDir(
                    activity,
                    Environment.DIRECTORY_DOWNLOADS,
                    URLUtil.guessFileName(url, disposition, mime),
                )
            }
            (activity.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
            onMessage("Download started")
        }.onFailure { onMessage("Download failed") }
    }

    private fun chromeLikeUserAgent(original: String): String {
        var value = original.replace("; wv)", ")").replace("Version/4.0 ", "")
        if (!value.contains("Chrome/")) {
            value += " Chrome/124.0.0.0 Mobile Safari/537.36"
        }
        return value
    }

    private companion object {
        /**
         * Finds the most likely prompt box on the page and types into it using
         * the framework's own setters so React/Lexical/ProseMirror editors
         * notice the change.
         */
        val INJECT_SCRIPT = """
            (function () {
              try {
                var text = __TEXT__;
                function usable(el) {
                  if (!el) return false;
                  var rect = el.getBoundingClientRect();
                  if (rect.width < 40 || rect.height < 10) return false;
                  var style = getComputedStyle(el);
                  return style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
                }
                var nodes = Array.prototype.slice.call(
                  document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"], [role="textbox"]')
                ).filter(usable);
                if (!nodes.length) return 'none';
                nodes.sort(function (a, b) {
                  var ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
                  return (rb.width * rb.height) - (ra.width * ra.height);
                });
                var el = nodes[0];
                el.focus();
                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                  var proto = el.tagName === 'TEXTAREA'
                    ? window.HTMLTextAreaElement.prototype
                    : window.HTMLInputElement.prototype;
                  var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                  setter.call(el, text);
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                } else {
                  var selection = window.getSelection();
                  var range = document.createRange();
                  range.selectNodeContents(el);
                  selection.removeAllRanges();
                  selection.addRange(range);
                  document.execCommand('insertText', false, text);
                  el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
                }
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return 'ok';
              } catch (error) {
                return 'error';
              }
            })()
        """.trimIndent()
    }
}
