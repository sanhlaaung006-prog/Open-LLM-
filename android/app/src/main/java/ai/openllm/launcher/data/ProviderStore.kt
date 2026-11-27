package ai.openllm.launcher.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persists enable/reorder/custom-site edits in SharedPreferences as JSON.
 *
 * Stored entries are merged onto [ProviderCatalog.defaults] by id, so a new app
 * version can ship a new provider (or fix a URL) without wiping user settings.
 */
class ProviderStore(context: Context) {

    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun load(): List<Provider> {
        val raw = prefs.getString(KEY_PROVIDERS, null) ?: return ProviderCatalog.defaults
        return runCatching { decode(raw) }.getOrDefault(ProviderCatalog.defaults)
    }

    fun save(providers: List<Provider>) {
        prefs.edit().putString(KEY_PROVIDERS, encode(providers).toString()).apply()
    }

    fun reset(): List<Provider> {
        prefs.edit().remove(KEY_PROVIDERS).apply()
        return ProviderCatalog.defaults
    }

    private fun encode(providers: List<Provider>): JSONArray {
        val array = JSONArray()
        providers.forEach { p ->
            array.put(
                JSONObject().apply {
                    put("id", p.id)
                    put("name", p.name)
                    put("homeUrl", p.homeUrl)
                    put("promptUrlTemplate", p.promptUrlTemplate ?: JSONObject.NULL)
                    put("color", p.color)
                    put("monogram", p.monogram)
                    put("userAgentMode", p.userAgentMode.name)
                    put("enabled", p.enabled)
                    put("custom", p.custom)
                }
            )
        }
        return array
    }

    private fun decode(raw: String): List<Provider> {
        val array = JSONArray(raw)
        val result = ArrayList<Provider>(array.length())
        for (index in 0 until array.length()) {
            val json = array.optJSONObject(index) ?: continue
            val id = json.optString("id").ifBlank { continue }
            val enabled = json.optBoolean("enabled", true)
            val custom = json.optBoolean("custom", false)

            val base = if (custom) {
                Provider(
                    id = id,
                    name = json.optString("name", "Custom"),
                    homeUrl = json.optString("homeUrl", ""),
                    promptUrlTemplate = json.optString("promptUrlTemplate").takeIf {
                        it.isNotBlank() && it != "null"
                    },
                    color = json.optLong("color", ProviderCatalog.customColors.first()),
                    monogram = json.optString("monogram", "AI"),
                    custom = true,
                )
            } else {
                ProviderCatalog.byId(id) ?: continue
            }

            val uaMode = runCatching {
                UserAgentMode.valueOf(json.optString("userAgentMode", base.userAgentMode.name))
            }.getOrDefault(base.userAgentMode)

            // Name/URL for shipped providers always come from the catalog so
            // upstream fixes reach existing installs; only user knobs persist.
            result.add(base.copy(enabled = enabled, userAgentMode = uaMode))
        }
        // Any shipped provider missing from storage is appended in catalog order
        // (happens the first time a new app version adds a site).
        ProviderCatalog.defaults.forEach { shipped ->
            if (result.none { it.id == shipped.id }) result.add(shipped)
        }
        return result
    }

    private companion object {
        const val PREFS = "openllm.providers"
        const val KEY_PROVIDERS = "providers.v1"
    }
}
