# Point this shell at the toolchain setup_windows.ps1 installed. Every cache
# (Gradle, pub, Android user home, temp) lives under -Root, never on C:.
param([string]$Root = "D:\dev")

$env:JAVA_HOME = "$Root\jdk-17"
$env:ANDROID_HOME = "$Root\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:ANDROID_USER_HOME = "$Root\android-home"
$env:GRADLE_USER_HOME = "$Root\gradle-home"
$env:PUB_CACHE = "$Root\pub-cache"
$env:TEMP = "$Root\tmp"
$env:TMP = "$Root\tmp"
$env:FLUTTER_SUPPRESS_ANALYTICS = "true"
$env:Path = "$Root\flutter\bin;$Root\jdk-17\bin;$Root\android-sdk\platform-tools;" + $env:Path
