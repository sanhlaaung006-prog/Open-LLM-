package ai.openllm.launcher

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import ai.openllm.launcher.data.Provider
import ai.openllm.launcher.data.ProviderCatalog
import ai.openllm.launcher.data.ProviderStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale
import java.util.UUID

class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val store = ProviderStore(app)

    private val _providers = MutableStateFlow(store.load())
    val providers: StateFlow<List<Provider>> = _providers.asStateFlow()

    private val _activeId = MutableStateFlow(
        _providers.value.firstOrNull { it.enabled }?.id.orEmpty(),
    )
    val activeId: StateFlow<String> = _activeId.asStateFlow()

    /** Prompts waiting to be handed to a provider (used for "send to all"). */
    private val _queued = MutableStateFlow<Map<String, String>>(emptyMap())
    val queued: StateFlow<Map<String, String>> = _queued.asStateFlow()

    // ------------------------------------------------------------ selection

    fun select(id: String) {
        _activeId.value = id
    }

    // ------------------------------------------------------------- composer

    /**
     * Hands [prompt] to every provider in [ids] and jumps to the first one.
     * Providers with a prefill URL open with the question already sent;
     * the rest get one-tap Paste.
     */
    fun broadcast(prompt: String, ids: List<String>) {
        if (prompt.isBlank() || ids.isEmpty()) return
        val trimmed = prompt.trim()
        _queued.value = _queued.value + ids.associateWith { trimmed }
        _activeId.value = ids.first()
    }

    fun clearQueued(id: String) {
        if (_queued.value.containsKey(id)) {
            _queued.value = _queued.value - id
        }
    }

    // ------------------------------------------------------------- settings

    fun setEnabled(id: String, enabled: Boolean) {
        update { list -> list.map { if (it.id == id) it.copy(enabled = enabled) else it } }
        ensureActiveEnabled()
    }

    fun move(id: String, delta: Int) {
        update { list ->
            val index = list.indexOfFirst { it.id == id }
            val target = index + delta
            if (index < 0 || target !in list.indices) {
                list
            } else {
                list.toMutableList().apply { add(target, removeAt(index)) }
            }
        }
    }

    fun addCustom(name: String, url: String): Boolean {
        val cleanName = name.trim()
        val cleanUrl = normaliseUrl(url)
        if (cleanName.isEmpty() || cleanUrl == null) return false
        if (_providers.value.any { it.homeUrl == cleanUrl }) return false

        val palette = ProviderCatalog.customColors
        val index = _providers.value.count { it.custom } % palette.size
        val provider = Provider(
            id = "custom-${UUID.randomUUID().toString().take(8)}",
            name = cleanName,
            homeUrl = cleanUrl,
            color = palette[index],
            monogram = monogramOf(cleanName),
            enabled = true,
            custom = true,
        )
        update { it + provider }
        return true
    }

    fun removeCustom(id: String) {
        update { list -> list.filterNot { it.id == id && it.custom } }
        ensureActiveEnabled()
    }

    fun resetToDefaults() {
        val fresh = store.reset()
        _providers.value = fresh
        _queued.value = emptyMap()
        _activeId.value = fresh.firstOrNull { it.enabled }?.id.orEmpty()
    }

    // --------------------------------------------------------------- helpers

    private fun update(transform: (List<Provider>) -> List<Provider>) {
        val next = transform(_providers.value)
        _providers.value = next
        store.save(next)
    }

    private fun ensureActiveEnabled() {
        val list = _providers.value
        val active = list.firstOrNull { it.id == _activeId.value }
        if (active == null || !active.enabled) {
            _activeId.value = list.firstOrNull { it.enabled }?.id.orEmpty()
        }
    }

    private fun normaliseUrl(input: String): String? {
        var value = input.trim()
        if (value.isEmpty()) return null
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "https://$value"
        }
        val host = runCatching { android.net.Uri.parse(value).host }.getOrNull()
        return if (host.isNullOrBlank()) null else value
    }

    private fun monogramOf(name: String): String {
        val letters = name.filter { it.isLetterOrDigit() }
        return letters.take(2).uppercase(Locale.getDefault()).ifEmpty { "AI" }
    }
}
