# FRB Launch integrated 0.9.3 PRIVATE_REVIEW local handshake test.
# Run AFTER rebuilding Launch with APP_VERSION=0.9.1.
# Creates NEW product ZIPs, stages product feed and configures TEST install.
# Never performs an update. Never overwrites already-published 0.9.3 ZIPs.
param(
    [string]$LaunchSource = 'F:\FRB_Apps\FRB_Launch',
    [string]$StudioSource = 'F:\FRB_Apps\FRB_Studio',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$RefreshConfigOnly,
    [switch]$ResumeAfterBuild
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($ResumeAfterBuild -and $RefreshConfigOnly) {
    throw 'Choose either -ResumeAfterBuild or -RefreshConfigOnly; these modes are mutually exclusive.'
}

$LaunchSource = [IO.Path]::GetFullPath($LaunchSource).TrimEnd('\')
$StudioSource = [IO.Path]::GetFullPath($StudioSource).TrimEnd('\')
$ReleaseDir = [IO.Path]::GetFullPath($ReleaseDir).TrimEnd('\')
$TestInstallRoot = [IO.Path]::GetFullPath($TestInstallRoot).TrimEnd('\')
if ($TestInstallRoot -notmatch '(?i)[\\/]FRB_Update_Test[\\/]FRBLaunch$') {
    throw "Safety guard: Only FRB_Update_Test\FRBLaunch may be configured: $TestInstallRoot"
}

$python = Join-Path $LaunchSource '.venv\Scripts\python.exe'
$launchExe = Join-Path $LaunchSource 'dist\FRBLaunch\FRBLaunch.exe'
$installedExe = Join-Path $TestInstallRoot 'FRBLaunch.exe'
$studioExe = Join-Path $StudioSource 'NativeShell\_publish\FRBStudio.NativeShell.exe'
$updaterExe = Join-Path $LaunchSource 'dist\updater\FRBUpdater.exe'
$builder = Join-Path $LaunchSource 'scripts\build_portable_distribution.py'
$appVersionFile = Join-Path $LaunchSource 'src\app_version.py'
$dialogSource = Join-Path $LaunchSource 'src\update_information_dialog.py'
$gateSource = Join-Path $LaunchSource 'src\frb_update\progress_gate.py'
$stateFile = Join-Path $TestInstallRoot 'installed_release.json'
$configFile = Join-Path $TestInstallRoot 'defs\update\update_sources.json'
$productZip = Join-Path $ReleaseDir 'FRBLaunch_0.9.3_PRIVATE_REVIEW_update.zip'
$portableZip = Join-Path $ReleaseDir 'FRBLaunch_0.9.3_PRIVATE_REVIEW_portable.zip'
$productFeed = Join-Path $ReleaseDir 'product_feed.json'
$updaterFeed = Join-Path $ReleaseDir 'updater_feed.json'
$updaterArtifact = Join-Path $ReleaseDir 'FRBUpdater_0.9.3.exe'

foreach ($required in @($stateFile, $configFile, $installedExe, $updaterFeed, $updaterArtifact)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing: $required" }
}
$state = Get-Content -LiteralPath $stateFile -Encoding UTF8 -Raw | ConvertFrom-Json
if ([string]$state.version -notin @('0.9.2', '0.9.3')) {
    throw "Expected test installation integrated 0.9.2 or 0.9.3; got $($state.version)"
}
$updater = Get-Content -LiteralPath $updaterFeed -Encoding UTF8 -Raw | ConvertFrom-Json
if ($updater.schema -ne 'frb-updater-feed-v1' -or $updater.version -ne '0.9.3') {
    throw 'Updater feed must point to 0.9.3 (stage_FRBUpdater_0.9.3_progress_test.ps1 first).'
}
$updaterHash = (Get-FileHash -LiteralPath $updaterArtifact -Algorithm SHA256).Hash.ToLowerInvariant()
if ($updaterHash -ne [string]$updater.sha256) {
    throw 'Staged FRBUpdater_0.9.3.exe SHA-256 disagrees with updater_feed.json.'
}
# Never prepare a new update over an unfinished recovery Journal.
$backupRoot = Join-Path (Split-Path -Parent $TestInstallRoot) '.FRBLaunch_update_backups'
if (Test-Path -LiteralPath $backupRoot) {
    foreach ($file in @(Get-ChildItem -LiteralPath $backupRoot -File -Filter journal.json -Recurse)) {
        $journal = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -Raw | ConvertFrom-Json
        if ($journal.phase -eq 'applying') {
            throw "An interrupted update must be recovered first: $($file.FullName)"
        }
    }
}

if (-not $RefreshConfigOnly) {
    if ($state.version -ne '0.9.2') {
        throw 'New release preparation requires the TEST install to remain at integrated 0.9.2.'
    }
    foreach ($required in @($python, $launchExe, $studioExe, $updaterExe, $builder, $appVersionFile, $dialogSource, $gateSource)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing: $required" }
    }
    if ($ResumeAfterBuild) {
        # Reuse previously completed, immutable PRIVATE_REVIEW archives.
        foreach ($requiredZip in @($productZip, $portableZip)) {
            if (-not (Test-Path -LiteralPath $requiredZip -PathType Leaf)) {
                throw "Resume needs the already-built 0.9.3 ZIP: $requiredZip"
            }
        }
    } elseif ((Test-Path -LiteralPath $productZip) -or (Test-Path -LiteralPath $portableZip)) {
        throw '0.9.3 ZIP already exists. To verify and resume without rebuilding, use -ResumeAfterBuild.'
    }
    $sourceVersion = Get-Content -LiteralPath $appVersionFile -Encoding UTF8 -Raw
    if ($sourceVersion -notmatch "(?m)^APP_VERSION\s*=\s*'0\.9\.1'\s*$") {
        throw 'src/app_version.py must declare APP_VERSION = 0.9.1 before the Launch rebuild.'
    }
    $dialogText = Get-Content -LiteralPath $dialogSource -Encoding UTF8 -Raw
    if (-not $dialogText.Contains('self._ready_timer.start()') -or -not $dialogText.Contains('activate(ready)')) {
        throw 'Launch handshake code is missing from src/update_information_dialog.py.'
    }
    # Fail rather than accidentally shipping an EXE from before the change.
    $exeMtime = (Get-Item -LiteralPath $launchExe).LastWriteTimeUtc
    foreach ($source in @($appVersionFile, $dialogSource, $gateSource)) {
        if ($exeMtime -lt (Get-Item -LiteralPath $source).LastWriteTimeUtc) {
            throw "Launch EXE is older than patched source. Run _build_windows.bat again: $source"
        }
    }
    $binaryHash = (Get-FileHash -LiteralPath $launchExe -Algorithm SHA256).Hash.ToLowerInvariant()
    $installedHash = (Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($binaryHash -eq $installedHash) {
        throw 'Launch EXE equals installed 0.9.2 EXE: stale build detected. Rebuild Launch before release.'
    }
    $studioVersion = [string]$state.components.studio
    if ($studioVersion -ne '0.9.0') {
        throw "This scenario expects Studio 0.9.0; installed manifest reports $studioVersion"
    }

    if ($ResumeAfterBuild) {
        Write-Host '[1/3] Reuse existing PRIVATE_REVIEW 0.9.3 ZIPs (no build, no overwrite)...' -ForegroundColor Cyan
    } else {
        Write-Host '[1/3] Create new PRIVATE_REVIEW integrated 0.9.3 ZIPs...' -ForegroundColor Cyan
        Write-Host 'Integrated=0.9.3 / Launch=0.9.1 / Studio=0.9.0 / Updater=0.9.3'
        $argv = @($builder,
            '--launch-source', $LaunchSource,
            '--studio-source', $StudioSource,
            '--output', $ReleaseDir,
            '--version', '0.9.3',
            '--launch-version', '0.9.1',
            '--studio-version', '0.9.0',
            '--updater-version', '0.9.3',
            '--notes', 'Launch 0.9.1 progress UI readiness handshake / PRIVATE REVIEW ONLY')
        & $python @argv
        if ($LASTEXITCODE -ne 0) { throw "Release builder failed with exit code $LASTEXITCODE" }
    }
}
if (-not (Test-Path -LiteralPath $productZip -PathType Leaf)) { throw "Missing update ZIP: $productZip" }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($productZip)
try {
    $entry = $archive.GetEntry('release.json')
    if ($null -eq $entry) { throw 'release.json is missing from update ZIP.' }
    $reader = [IO.StreamReader]::new($entry.Open(), [Text.Encoding]::UTF8)
    try { $manifest = $reader.ReadToEnd() | ConvertFrom-Json }
    finally { $reader.Dispose() }
} finally { $archive.Dispose() }
if ($manifest.schema -ne 'frb-system-package-v1' -or $manifest.product -ne 'FRBLaunchIntegrated') {
    throw 'Release manifest schema/product mismatch.'
}
if ($manifest.version -ne '0.9.3' -or $manifest.components.launch -ne '0.9.1' -or $manifest.components.studio -ne '0.9.0') {
    throw 'Release manifest versions differ from the expected 0.9.3 / 0.9.1 / 0.9.0.'
}
if (-not $RefreshConfigOnly) {
    if ([string]$manifest.files.'FRBLaunch.exe' -ne $binaryHash) {
        throw 'The ZIP does not contain the newly built Launch EXE (SHA-256 differs).'
    }
    Write-Host '[2/3] Stage local product Feed (backup old Feed)...' -ForegroundColor Cyan
    if (Test-Path -LiteralPath $productFeed -PathType Leaf) {
        $feedBackup = $productFeed + '.before_093_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak'
        Copy-Item -LiteralPath $productFeed -Destination $feedBackup -ErrorAction Stop
        Write-Host "[BACKUP] $feedBackup"
    }
    $product = [ordered]@{
        schema = 'frb-product-feed-v1'
        product = 'FRBLaunchIntegrated'
        version = '0.9.3'
        components = $manifest.components
        notes = 'Launch 0.9.1 handshake visibility test; PRIVATE REVIEW ONLY'
        archive_url = 'file:///' + $productZip.Replace('\', '/')
        size = (Get-Item -LiteralPath $productZip).Length
        sha256 = (Get-FileHash -LiteralPath $productZip -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    [IO.File]::WriteAllText($productFeed, (($product | ConvertTo-Json -Depth 8) + "`n"), (New-Object Text.UTF8Encoding($false)))
}

Write-Host '[3/3] Configure local TEST Feed URLs (backup installed config)...' -ForegroundColor Cyan
$product = Get-Content -LiteralPath $productFeed -Encoding UTF8 -Raw | ConvertFrom-Json
if ($product.version -ne '0.9.3' -or $product.components.launch -ne '0.9.1') {
    throw 'Product Feed must reference integrated 0.9.3 and Launch 0.9.1.'
}
if ([string]$product.sha256 -ne (Get-FileHash -LiteralPath $productZip -Algorithm SHA256).Hash.ToLowerInvariant()) {
    throw 'Product Feed SHA-256 does not match release ZIP.'
}
$configBackup = $configFile + '.before_093_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak'
Copy-Item -LiteralPath $configFile -Destination $configBackup -ErrorAction Stop
$sources = [ordered]@{
    schema = 'frb-update-sources-v1'
    updater_feed_url = 'file:///' + $updaterFeed.Replace('\', '/')
    product_feed_url = 'file:///' + $productFeed.Replace('\', '/')
    allow_local_for_test = $true
}
[IO.File]::WriteAllText($configFile, (($sources | ConvertTo-Json -Depth 5) + "`n"), (New-Object Text.UTF8Encoding($false)))
Write-Host "[BACKUP] $configBackup"
Write-Host "[OK] Integrated currently installed: $($state.version)" -ForegroundColor Green
Write-Host '[OK] Feeds: product 0.9.3 (Launch 0.9.1) / Updater 0.9.3' -ForegroundColor Green
Write-Host '[SAFE] No update started; no Journal or product files modified.' -ForegroundColor Green
if ($RefreshConfigOnly) {
    Write-Host '[NEXT] Launch TEST EXE and check latest: it should say 0.9.3 is current.'
} else {
    Write-Host '[NEXT] Start TEST Launch 0.9.2 > Check latest > Update ONCE.'
    Write-Host '[CHECK] Updater native progress window visible BEFORE Launch exits.'
    Write-Host '[NOTE] After updating, use -RefreshConfigOnly if the installed Feed config was overwritten.'
}
