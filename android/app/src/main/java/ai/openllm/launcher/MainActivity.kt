package ai.openllm.launcher

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import ai.openllm.launcher.ui.AppRoot
import ai.openllm.launcher.ui.OpenLLMTheme
import ai.openllm.launcher.web.WebViewPool

class MainActivity : ComponentActivity() {

    private lateinit var pool: WebViewPool
    private val viewModel: AppViewModel by viewModels()

    /** Text handed to us by another app (share sheet / text selection). */
    private var sharedText by mutableStateOf<String?>(null)
    private var pendingPermission: PermissionRequest? = null

    private val filePicker =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            pool.deliverFileChosen(
                WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data),
            )
        }

    private val microphone =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            val request = pendingPermission
            pendingPermission = null
            if (request == null) return@registerForActivityResult
            if (granted) {
                request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
            } else {
                request.deny()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        pool = WebViewPool(
            activity = this,
            onFileChooser = { params ->
                runCatching { filePicker.launch(params.createIntent()) }
                    .onFailure {
                        pool.deliverFileChosen(null)
                        toast("No file picker available")
                    }
            },
            onPermissionRequest = { request -> handlePermission(request) },
            onOpenExternal = { url -> openExternally(url) },
            onMessage = { message -> toast(message) },
        )

        sharedText = extractText(intent)

        setContent {
            val dark = isSystemInDarkTheme()
            OpenLLMTheme(darkTheme = dark) {
                AppRoot(
                    pool = pool,
                    vm = viewModel,
                    initialPrompt = sharedText,
                    onInitialPromptConsumed = { sharedText = null },
                    onExit = { finish() },
                    darkTheme = dark,
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        extractText(intent)?.let { sharedText = it }
    }

    override fun onDestroy() {
        pool.destroy()
        super.onDestroy()
    }

    private fun handlePermission(request: PermissionRequest) {
        val wantsAudio = request.resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)
        val wantsVideo = request.resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)
        // Microphone powers voice input; camera requests are declined.
        if (!wantsAudio || wantsVideo) {
            request.deny()
            return
        }
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED

        if (granted) {
            request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
        } else {
            pendingPermission = request
            microphone.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun openExternally(url: String) {
        runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
            .onFailure { toast("No browser available") }
    }

    private fun extractText(intent: Intent?): String? = when (intent?.action) {
        Intent.ACTION_SEND -> intent.getStringExtra(Intent.EXTRA_TEXT)
        Intent.ACTION_PROCESS_TEXT ->
            intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString()
        else -> null
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}
