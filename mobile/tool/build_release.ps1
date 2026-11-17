# Signed, obfuscated release APKs (one per CPU type) + a universal one.
#
#   powershell -ExecutionPolicy Bypass -File mobile\tool\build_release.ps1 [-KeyProperties D:\path\key.properties]
#
# The signing key lives OUTSIDE the repository (default
# D:\projects\Ketoshop-keys\key.properties). Without it the build is
# signed with the debug key and must not be given to customers.
param(
    [string]$KeyProperties = "D:\projects\Ketoshop-keys\key.properties",
    [string]$Root = "D:\dev",
    [string]$Version = "1.0.0",
    [int]$Build = 1
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "env.ps1") -Root $Root
$mobile = Split-Path $PSScriptRoot -Parent
Set-Location $mobile

if (Test-Path $KeyProperties) { $env:KETOSHOP_KEY_PROPERTIES = $KeyProperties }
else { Write-Warning "No key.properties at $KeyProperties - building with the DEBUG key." }

python (Join-Path $PSScriptRoot "gen_l10n.py")
if ($LASTEXITCODE -ne 0) { throw "gen_l10n failed" }

flutter pub get
# Infos don't stop the build (Flutter 3.47+ marks the material.dart import
# itself deprecated); warnings and errors do.
flutter analyze --no-fatal-infos
if ($LASTEXITCODE -ne 0) { throw "flutter analyze found problems" }
flutter test
if ($LASTEXITCODE -ne 0) { throw "tests failed" }

$common = @(
    "--release", "--obfuscate", "--split-debug-info=build/symbols",
    "--build-name=$Version", "--build-number=$Build",
    "--dart-define=KS_VERSION=$Version", "--dart-define=KS_BUILD=$Build"
)
flutter build apk @common --split-per-abi
if ($LASTEXITCODE -ne 0) { throw "split build failed" }
flutter build apk @common
if ($LASTEXITCODE -ne 0) { throw "universal build failed" }

Get-ChildItem build\app\outputs\flutter-apk\*.apk | ForEach-Object {
    $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
    "{0,-40} {1,8:N1} MB  sha256 {2}" -f $_.Name, ($_.Length / 1MB), $hash
}
