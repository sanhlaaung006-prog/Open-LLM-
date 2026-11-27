package ai.openllm.launcher.ui

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val Indigo = Color(0xFF4F46E5)
private val IndigoLight = Color(0xFF6366F1)

private val LightColors = lightColorScheme(
    primary = Indigo,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE0E7FF),
    onPrimaryContainer = Color(0xFF1E1B4B),
    secondary = Color(0xFF0F766E),
    secondaryContainer = Color(0xFFE4F0FF),
    onSecondaryContainer = Color(0xFF0B2A4A),
    background = Color(0xFFFDFDFF),
    onBackground = Color(0xFF111114),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF111114),
    surfaceVariant = Color(0xFFF1F1F5),
    onSurfaceVariant = Color(0xFF5B5B66),
    outline = Color(0xFFD8D8E0),
)

private val DarkColors = darkColorScheme(
    primary = IndigoLight,
    onPrimary = Color(0xFF0B0B12),
    primaryContainer = Color(0xFF2A2A6B),
    onPrimaryContainer = Color(0xFFE0E7FF),
    secondary = Color(0xFF7DD3FC),
    secondaryContainer = Color(0xFF1B2A3A),
    onSecondaryContainer = Color(0xFFD6E9FF),
    background = Color(0xFF0B0B0F),
    onBackground = Color(0xFFEDEDF2),
    surface = Color(0xFF121218),
    onSurface = Color(0xFFEDEDF2),
    surfaceVariant = Color(0xFF1D1D25),
    onSurfaceVariant = Color(0xFFA6A6B4),
    outline = Color(0xFF33333D),
)

@Composable
fun OpenLLMTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val view = LocalView.current
    LaunchedEffect(darkTheme) {
        val window = (view.context as? Activity)?.window ?: return@LaunchedEffect
        WindowCompat.getInsetsController(window, view).apply {
            isAppearanceLightStatusBars = !darkTheme
            isAppearanceLightNavigationBars = !darkTheme
        }
    }
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
