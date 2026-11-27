package ai.openllm.launcher.data

/**
 * The shipped provider list.
 *
 * `promptUrlTemplate` values are best-effort: they are the URLs the sites
 * themselves use for "start a chat with this question". If a site changes its
 * query parameter the tab simply opens at the home page and the app offers the
 * Paste button instead - nothing breaks.
 */
object ProviderCatalog {

    val defaults: List<Provider> = listOf(
        Provider(
            id = "chatgpt",
            name = "ChatGPT",
            homeUrl = "https://chatgpt.com/",
            promptUrlTemplate = "https://chatgpt.com/?q={prompt}",
            color = 0xFF10A37F,
            monogram = "GP",
        ),
        Provider(
            id = "claude",
            name = "Claude",
            homeUrl = "https://claude.ai/new",
            promptUrlTemplate = "https://claude.ai/new?q={prompt}",
            color = 0xFFD97757,
            monogram = "CL",
        ),
        Provider(
            id = "gemini",
            name = "Gemini",
            homeUrl = "https://gemini.google.com/app",
            color = 0xFF4285F4,
            monogram = "GM",
        ),
        Provider(
            id = "grok",
            name = "Grok",
            homeUrl = "https://grok.com/",
            promptUrlTemplate = "https://grok.com/?q={prompt}",
            color = 0xFF4B5563,
            monogram = "GK",
        ),
        Provider(
            id = "perplexity",
            name = "Perplexity",
            homeUrl = "https://www.perplexity.ai/",
            promptUrlTemplate = "https://www.perplexity.ai/search?q={prompt}",
            color = 0xFF20808D,
            monogram = "PX",
        ),
        Provider(
            id = "copilot",
            name = "Copilot",
            homeUrl = "https://copilot.microsoft.com/",
            promptUrlTemplate = "https://copilot.microsoft.com/?q={prompt}",
            color = 0xFF0F6CBD,
            monogram = "CO",
        ),
        Provider(
            id = "deepseek",
            name = "DeepSeek",
            homeUrl = "https://chat.deepseek.com/",
            color = 0xFF4D6BFE,
            monogram = "DS",
        ),
        Provider(
            id = "qwen",
            name = "Qwen",
            homeUrl = "https://chat.qwen.ai/",
            color = 0xFF615CED,
            monogram = "QW",
        ),
        Provider(
            id = "kimi",
            name = "Kimi",
            homeUrl = "https://www.kimi.com/",
            color = 0xFF2F6BFF,
            monogram = "KM",
        ),
        Provider(
            id = "metaai",
            name = "Meta AI",
            homeUrl = "https://www.meta.ai/",
            color = 0xFF0866FF,
            monogram = "MA",
        ),
        Provider(
            id = "mistral",
            name = "Le Chat",
            homeUrl = "https://chat.mistral.ai/chat",
            color = 0xFFFF7000,
            monogram = "MS",
        ),
        Provider(
            id = "poe",
            name = "Poe",
            homeUrl = "https://poe.com/",
            color = 0xFF5D3FD3,
            monogram = "PO",
        ),
        Provider(
            id = "you",
            name = "You.com",
            homeUrl = "https://you.com/",
            promptUrlTemplate = "https://you.com/search?q={prompt}",
            color = 0xFF7C3AED,
            monogram = "YU",
        ),
    )

    /** Palette used for user-added sites. */
    val customColors: List<Long> = listOf(
        0xFF4F46E5, 0xFF0891B2, 0xFFDB2777, 0xFF059669, 0xFFEA580C, 0xFF7C3AED,
    )

    fun byId(id: String): Provider? = defaults.firstOrNull { it.id == id }
}
