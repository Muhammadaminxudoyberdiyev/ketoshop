# Ketoshop mobile toolchain for Windows: JDK 17, Flutter, Android SDK.
#
# Everything goes under -Root (default D:\dev) - nothing is written to C:.
# Every download is checked against a pinned checksum before it is unpacked;
# a mismatch stops the script. Re-running skips what is already installed.
#
#   powershell -ExecutionPolicy Bypass -File mobile\tool\setup_windows.ps1
#   . mobile\tool\env.ps1      # then, in each new shell
param([string]$Root = "D:\dev")

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Jdk = @{
    Url    = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.21%2B9/OpenJDK17U-jdk_x64_windows_hotspot_17.0.21_9.zip"
    Sha256 = "98518ecf554465057ee5509462631deeee374bc368c12a411d225cd29381f84b"
    Dir    = "jdk-17"
}
$Flutter = @{
    Url    = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.50.0-stable.zip"
    Sha256 = "35fb843409c80a1c69b64bbae1756bba437222f909622d83540e266e1759aab8"
    Dir    = "flutter"
}
$CmdlineTools = @{
    Url  = "https://dl.google.com/android/repository/commandlinetools-win-16111833_latest.zip"
    Sha1 = "57d04f2d75eb8e8fffc5000a987e5de4b5a63e9d"
}
# cmdline-tools 23 hands off to the new Android CLI, whose package ids use
# "/" (platforms/android-36). Gradle's own auto-download still asks for
# "ndk;<ver>", which that CLI rejects, so the NDK Flutter 3.50 pins
# (flutter.ndkVersion) is installed here.
$SdkPackages = @("platform-tools", "platforms/android-36", "build-tools/36.0.0", "ndk/28.2.13676358")

New-Item -ItemType Directory -Force -Path $Root, "$Root\downloads", "$Root\tmp" | Out-Null

function Get-Checked([string]$Url, [string]$Algorithm, [string]$Expected) {
    $file = Join-Path "$Root\downloads" ([IO.Path]::GetFileName(([uri]$Url).LocalPath))
    if (-not (Test-Path $file) -or (Get-FileHash $file -Algorithm $Algorithm).Hash -ne $Expected.ToUpper()) {
        Write-Host "Downloading $Url"
        # -C - resumes a partial file; the checksum below catches any damage.
        & curl.exe -fL --retry 8 --retry-all-errors --retry-delay 5 -C - -o $file $Url
        if ($LASTEXITCODE -ne 0) { throw "download failed: $Url" }
    }
    $actual = (Get-FileHash $file -Algorithm $Algorithm).Hash
    if ($actual -ne $Expected.ToUpper()) {
        Remove-Item $file -Force
        throw "$Algorithm mismatch for $Url (got $actual)"
    }
    return $file
}

function Expand-Into([string]$Zip, [string]$Target) {
    $staging = Join-Path "$Root\tmp" ([guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    & tar.exe -xf $Zip -C $staging
    if ($LASTEXITCODE -ne 0) { throw "unpack failed: $Zip" }
    $inner = Get-ChildItem $staging
    if ($inner.Count -eq 1 -and $inner[0].PSIsContainer) { Move-Item $inner[0].FullName $Target }
    else { Move-Item $staging $Target }
    Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path "$Root\$($Jdk.Dir)\bin\java.exe")) {
    Expand-Into (Get-Checked $Jdk.Url "SHA256" $Jdk.Sha256) "$Root\$($Jdk.Dir)"
}
if (-not (Test-Path "$Root\$($Flutter.Dir)\bin\flutter.bat")) {
    Expand-Into (Get-Checked $Flutter.Url "SHA256" $Flutter.Sha256) "$Root\$($Flutter.Dir)"
}
$sdk = "$Root\android-sdk"
if (-not (Test-Path "$sdk\cmdline-tools\latest\bin\sdkmanager.bat")) {
    New-Item -ItemType Directory -Force -Path "$sdk\cmdline-tools" | Out-Null
    Expand-Into (Get-Checked $CmdlineTools.Url "SHA1" $CmdlineTools.Sha1) "$sdk\cmdline-tools\latest"
}

. (Join-Path $PSScriptRoot "env.ps1") -Root $Root

# Licences are accepted non-interactively so Gradle can fetch what it needs.
$yes = ("y`n" * 40)
$yes | & "$sdk\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root=$sdk --licenses | Out-Null
& "$sdk\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root=$sdk @SdkPackages
if ($LASTEXITCODE -ne 0) { throw "sdkmanager failed" }

& flutter config --no-analytics --android-sdk $sdk --jdk-dir "$Root\$($Jdk.Dir)" | Out-Null
& flutter --disable-analytics | Out-Null
& flutter precache --android --no-ios --no-web --no-linux --no-windows --no-macos --no-fuchsia
& flutter doctor -v
