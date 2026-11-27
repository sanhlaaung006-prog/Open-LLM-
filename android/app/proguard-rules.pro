# Keep Compose runtime metadata.
-keep class androidx.compose.runtime.** { *; }

# WebView JS bridge is not used, but keep annotations for Compose previews.
-dontwarn org.jetbrains.annotations.**
