[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBaseUrl,

    [string]$FlutterExecutable = 'flutter',

    [switch]$AllowDevelopmentSigning
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$apiUri = $null
if (-not [Uri]::TryCreate($ApiBaseUrl, [UriKind]::Absolute, [ref]$apiUri) -or
    $apiUri.Scheme -ne 'https') {
    throw 'ApiBaseUrl must be an absolute HTTPS URL, for example https://owner-attendx-api.hf.space'
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$flutterProject = Join-Path $repositoryRoot 'frontend\attendx'
$keyProperties = Join-Path $flutterProject 'android\key.properties'
$outputDirectory = Join-Path $repositoryRoot 'dist\huggingface-web'
$flutterCommand = (Get-Command $FlutterExecutable -ErrorAction Stop).Source

if (-not (Test-Path -LiteralPath $keyProperties) -and -not $AllowDevelopmentSigning) {
    throw @'
Android release signing is not configured. Copy android/key.properties.example
to android/key.properties and point it at a private keystore. For a presentation-
only APK, rerun with -AllowDevelopmentSigning.
'@
}

function Invoke-Flutter {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & $flutterCommand @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter failed: flutter $($Arguments -join ' ')"
    }
}

Push-Location $flutterProject
try {
    Invoke-Flutter pub get
    Invoke-Flutter build web --release `
        "--dart-define=API_BASE_URL=$($apiUri.AbsoluteUri.TrimEnd('/'))" `
        '--dart-define=MOBILE_APP_DOWNLOAD_URL=AttendX.apk'
    Invoke-Flutter build apk --release `
        "--dart-define=API_BASE_URL=$($apiUri.AbsoluteUri.TrimEnd('/'))"
}
finally {
    Pop-Location
}

if (Test-Path -LiteralPath $outputDirectory) {
    Remove-Item -LiteralPath $outputDirectory -Recurse -Force
}
New-Item -ItemType Directory -Path $outputDirectory | Out-Null

$webBuild = Join-Path $flutterProject 'build\web'
$apkBuild = Join-Path $flutterProject 'build\app\outputs\flutter-apk\app-release.apk'
Copy-Item -Path (Join-Path $webBuild '*') -Destination $outputDirectory -Recurse
Copy-Item -LiteralPath $apkBuild -Destination (Join-Path $outputDirectory 'AttendX.apk')

@'
---
title: AttendX
emoji: 📍
colorFrom: green
colorTo: gray
sdk: static
app_file: index.html
pinned: false
---

# AttendX

Low-bandwidth web client and Android download for AttendX.
'@ | Set-Content -LiteralPath (Join-Path $outputDirectory 'README.md') -Encoding utf8

Write-Host "Hugging Face Static Space package: $outputDirectory"
