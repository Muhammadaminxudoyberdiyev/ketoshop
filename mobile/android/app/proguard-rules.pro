# R8: shrink, optimize and rename everything that isn't reached by name.
# Flutter's own keep rules come from its Gradle plugin; our Kotlin is only
# reached through the manifest (MainActivity), which AAPT keeps.
-repackageclasses ''
-allowaccessmodification
-overloadaggressively

# No android.util.Log calls survive in a release build.
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
    public static int w(...);
    public static int e(...);
    public static int wtf(...);
}

# Flutter's embedding references Play Core for deferred components, which
# this app does not use.
-dontwarn com.google.android.play.core.**
