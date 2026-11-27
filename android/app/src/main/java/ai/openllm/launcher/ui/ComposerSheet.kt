package ai.openllm.launcher.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ai.openllm.launcher.data.Provider

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ComposerSheet(
    providers: List<Provider>,
    initialText: String,
    onDismiss: () -> Unit,
    onSend: (String, List<String>) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val keyboard = LocalSoftwareKeyboardController.current
    var text by remember { mutableStateOf(initialText) }
    val selected = remember(providers) {
        mutableStateListOf(*providers.map { it.id }.toTypedArray())
    }

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .imePadding()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp),
        ) {
            Text(
                text = "Ask every model",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "One prompt, opened in each selected chat.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(14.dp))
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Ask anything...") },
                minLines = 3,
                maxLines = 8,
                shape = RoundedCornerShape(16.dp),
            )

            Spacer(Modifier.height(14.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "${selected.size} of ${providers.size} selected",
                    style = MaterialTheme.typography.labelLarge,
                )
                Spacer(Modifier.width(8.dp))
                Spacer(Modifier.weight(1f))
                TextButton(
                    onClick = {
                        if (selected.size == providers.size) {
                            selected.clear()
                        } else {
                            selected.clear()
                            providers.forEach { selected.add(it.id) }
                        }
                    },
                ) {
                    Text(if (selected.size == providers.size) "None" else "All")
                }
            }

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(0.dp),
            ) {
                providers.forEach { provider ->
                    val isSelected = provider.id in selected
                    FilterChip(
                        selected = isSelected,
                        onClick = {
                            if (isSelected) selected.remove(provider.id)
                            else selected.add(provider.id)
                        },
                        label = { Text(provider.name) },
                        leadingIcon = {
                            Box(
                                Modifier
                                    .size(10.dp)
                                    .clip(CircleShape)
                                    .background(Color(provider.color)),
                            )
                        },
                    )
                }
            }

            val needsPaste = providers.filter { it.id in selected && !it.supportsPrefill }
            if (needsPaste.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "${needsPaste.joinToString { it.name }} open without the text - " +
                        "you get a one-tap Paste there.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Spacer(Modifier.height(18.dp))
            Button(
                onClick = {
                    val ids = providers.filter { it.id in selected }.map { it.id }
                    if (text.isNotBlank() && ids.isNotEmpty()) {
                        keyboard?.hide()
                        onSend(text.trim(), ids)
                        onDismiss()
                    }
                },
                enabled = text.isNotBlank() && selected.isNotEmpty(),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                shape = RoundedCornerShape(16.dp),
            ) {
                Icon(Icons.Filled.Send, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(10.dp))
                Text(
                    text = "Send to ${selected.size} model${if (selected.size == 1) "" else "s"}",
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
    }
}
