package ai.openllm.launcher.data

import android.net.Uri

/** How the WebView should present itself to the site. */
enum class UserAgentMode {
    /** Stock WebView user agent (contains "wv"). */
    WEBVIEW,

    /** Strip the WebView markers so sites treat us like Chrome. */
    CHROME_LIKE,
}

/**
 * One consumer AI chat site wrapped by the app.
 *
 * [promptUrlTemplate] is the site's "prefill" URL, if it has one: `{prompt}`
 * is replaced by the URL-encoded prompt. When it is null the app falls back to
 * the one-tap "Paste" button that injects the text into the page composer.
 */
data class Provider(
    val id: String,
    val name: String,
    val homeUrl: String,
    val promptUrlTemplate: String? = null,
    val color: Long,
    val monogram: String,
    val userAgentMode: UserAgentMode = UserAgentMode.WEBVIEW,
    val enabled: Boolean = true,
    val custom: Boolean = false,
) {
    /** True when the site can open with the prompt already in the box. */
    val supportsPrefill: Boolean
        get() = promptUrlTemplate?.contains("{prompt}") == true

    fun urlFor(prompt: String?): String {
        if (prompt.isNullOrBlank()) return homeUrl
        val template = promptUrlTemplate ?: return homeUrl
        // Uri.encode escapes spaces and query-breaking characters.
        return template.replace("{prompt}", Uri.encode(prompt))
    }
}
