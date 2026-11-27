package ai.openllm.launcher.ui

import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import ai.openllm.launcher.AppViewModel
import ai.openllm.launcher.data.Provider
import ai.openllm.launcher.web.WebViewPool

@Composable
fun AppRoot(
    pool: WebViewPool,
    vm: AppViewModel,
    initialPrompt: String?,
    onInitialPromptConsumed: () -> Unit,
    onExit: () -> Unit,
    darkTheme: Boolean,
) {
    val providers by vm.providers.collectAsState()
    val activeId by vm.activeId.collectAsState()
    val queued by vm.queued.collectAsState()
    val context = LocalContext.current

    var composerOpen by remember { mutableStateOf(false) }
    var settingsOpen by remember { mutableStateOf(false) }
    var composerText by remember { mutableStateOf("") }

    val enabled = remember(providers) { providers.filter { it.enabled } }
    val active = remember(enabled, activeId) {
        enabled.firstOrNull { it.id == activeId } ?: enabled.firstOrNull()
    }
    val pendingPrompt = active?.let { queued[it.id] }

    fun toast(msg: String) {
        Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
    }

    LaunchedEffect(darkTheme) { pool.applyDark(darkTheme) }

    // Text shared into the app (or selected with "Open-LLM" in another app).
    LaunchedEffect(initialPrompt) {
        if (!initialPrompt.isNullOrBlank()) {
            composerText = initialPrompt
            composerOpen = true
            onInitialPromptConsumed()
        }
    }

    // Load (or re-load) the active tab, handing it its queued prompt if any.
    LaunchedEffect(active?.id, pendingPrompt) {
        val provider = active ?: return@LaunchedEffect
        pool.show(provider, pendingPrompt)
        if (pendingPrompt != null && provider.supportsPrefill) {
            vm.clearQueued(provider.id)
        }
    }

    BackHandler {
        val provider = active
        if (provider == null || !pool.goBack(provider.id)) onExit()
    }

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Header(
            enabledCount = enabled.size,
            onReload = { active?.let { pool.reload(it.id) } },
            onSettings = { settingsOpen = true },
        )

        if (enabled.isEmpty()) {
            EmptyState(
                modifier = Modifier.weight(1f),
                onOpenSettings = { settingsOpen = true },
            )
        } else {
            ProviderStrip(
                providers = enabled,
                activeId = active?.id,
                queued = queued.keys,
                onSelect = { vm.select(it.id) },
            )

            val bannerProvider = active
            val bannerPrompt = pendingPrompt
            if (bannerProvider != null && bannerPrompt != null && !bannerProvider.supportsPrefill) {
                PendingPromptBanner(
                    provider = bannerProvider,
                    onPaste = {
                        pool.injectPrompt(bannerProvider.id, bannerPrompt) { ok ->
                            toast(
                                if (ok) "Pasted into ${bannerProvider.name}"
                                else "Couldn't find the chat box - long-press to paste",
                            )
                        }
                        vm.clearQueued(bannerProvider.id)
                    },
                    onDismiss = { vm.clearQueued(bannerProvider.id) },
                )
            }

            Box(Modifier.weight(1f).fillMaxWidth()) {
                WebViewHost(pool = pool, modifier = Modifier.fillMaxSize())
            }
        }

        AskBar(
            enabled = enabled.isNotEmpty(),
            onClick = { composerOpen = true },
        )
    }

    if (composerOpen) {
        ComposerSheet(
            providers = enabled,
            initialText = composerText,
            onDismiss = { composerOpen = false },
            onSend = { text, ids ->
                vm.broadcast(text, ids)
                composerText = ""
                val prefilled = enabled.count { it.id in ids && it.supportsPrefill }
                val needsPaste = ids.size - prefilled
                toast(
                    if (needsPaste == 0) "Sent to ${ids.size} model${plural(ids.size)}"
                    else "Sent to ${ids.size} - $needsPaste need one tap on Paste",
                )
            },
        )
    }

    if (settingsOpen) {
        SettingsSheet(
            providers = providers,
            onToggle = { id, on -> vm.setEnabled(id, on) },
            onMove = { id, delta -> vm.move(id, delta) },
            onRemove = { id -> vm.removeCustom(id) },
            onAdd = { name, url ->
                if (!vm.addCustom(name, url)) toast("That site couldn't be added")
            },
            onReset = {
                vm.resetToDefaults()
                toast("Model list reset")
            },
            onDismiss = { settingsOpen = false },
        )
    }
}

private fun plural(count: Int) = if (count == 1) "" else "s"

@Composable
private fun Header(enabledCount: Int, onReload: () -> Unit, onSettings: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .windowInsetsPadding(WindowInsets.statusBars)
            .padding(start = 20.dp, end = 6.dp, top = 6.dp, bottom = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                text = "Open-LLM",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = if (enabledCount == 0) "No models enabled"
                else "$enabledCount models in one place",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        IconButton(onClick = onReload) {
            Icon(Icons.Filled.Refresh, contentDescription = "Reload this page")
        }
        IconButton(onClick = onSettings) {
            Icon(Icons.Filled.Settings, contentDescription = "Manage models")
        }
    }
}

@Composable
private fun ProviderStrip(
    providers: List<Provider>,
    activeId: String?,
    queued: Set<String>,
    onSelect: (Provider) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        providers.forEach { provider ->
            val selected = provider.id == activeId
            Row(
                modifier = Modifier
                    .padding(end = 8.dp)
                    .clip(RoundedCornerShape(50))
                    .background(
                        if (selected) Color(provider.color)
                        else MaterialTheme.colorScheme.surfaceVariant,
                    )
                    .clickable { onSelect(provider) }
                    .padding(horizontal = 13.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier
                        .size(9.dp)
                        .clip(CircleShape)
                        .background(if (selected) Color.White else Color(provider.color)),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = provider.name,
                    color = if (selected) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 13.sp,
                    fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                    maxLines = 1,
                )
                if (provider.id in queued) {
                    Spacer(Modifier.width(6.dp))
                    Box(
                        Modifier
                            .size(6.dp)
                            .clip(CircleShape)
                            .background(if (selected) Color.White else Color(provider.color)),
                    )
                }
            }
        }
    }
}

@Composable
private fun PendingPromptBanner(
    provider: Provider,
    onPaste: () -> Unit,
    onDismiss: () -> Unit,
) {
    Surface(color = MaterialTheme.colorScheme.secondaryContainer, modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(start = 16.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = "Prompt ready for ${provider.name}",
                    style = MaterialTheme.typography.labelLarge,
                )
                Text(
                    text = "Tap Paste to drop it into the chat box",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.75f),
                )
            }
            TextButton(onClick = onPaste) { Text("Paste") }
            IconButton(onClick = onDismiss) {
                Icon(Icons.Filled.Close, contentDescription = "Dismiss", modifier = Modifier.size(18.dp))
            }
        }
    }
}

@Composable
private fun WebViewHost(pool: WebViewPool, modifier: Modifier = Modifier) {
    AndroidView(
        modifier = modifier,
        factory = { context ->
            FrameLayout(context).also { frame -> pool.attach(frame) }
        },
    )
}

@Composable
private fun AskBar(enabled: Boolean, onClick: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.surface, tonalElevation = 3.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.Center,
        ) {
            Button(
                onClick = onClick,
                enabled = enabled,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(14.dp),
            ) {
                Icon(Icons.Filled.Send, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(10.dp))
                Text("Ask every model")
            }
        }
    }
}

@Composable
private fun EmptyState(modifier: Modifier, onOpenSettings: () -> Unit) {
    Box(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("No models enabled", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(4.dp))
            Text(
                "Turn some back on to start chatting.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))
            Button(onClick = onOpenSettings) { Text("Choose models") }
        }
    }
}
