# FRB Launch integrated 0.9.2 LOCAL TEST release preparation.
# Builds release ZIPs from EXISTING prebuilt EXEs, stages product feed,
# configures only F:\FRB_Update_Test\FRBLaunch. Does not run an update.
param(
    [string]$LaunchSource = 'F:\FRB_Apps\FRB_Launch',
    [string]$StudioSource = 'F:\FRB_Apps\FRB_Studio',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$RefreshConfigOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$LaunchSource = [IO.Path]::GetFullPath($LaunchSource)
$StudioSource = [IO.Path]::GetFullPath($StudioSource)
$ReleaseDir = [IO.Path]::GetFullPath($ReleaseDir)
$TestInstallRoot = [IO.Path]::GetFullPath($TestInstallRoot).TrimEnd('\')
if ($TestInstallRoot -notmatch '(?i)[\\/]FRB_Update_Test[\\/]FRBLaunch$') {
    throw "Only the local test installation may be configured: $TestInstallRoot"
}

$python = Join-Path $LaunchSource '.venv\Scripts\python.exe'
$launchExe = Join-Path $LaunchSource 'dist\FRBLaunch\FRBLaunch.exe'
$updaterExe = Join-Path $LaunchSource 'dist\updater\FRBUpdater.exe'
$studioExe = Join-Path $StudioSource 'NativeShell\_publish\FRBStudio.NativeShell.exe'
$builder = Join-Path $LaunchSource 'scripts\build_portable_distribution.py'
$stateFile = Join-Path $TestInstallRoot 'installed_release.json'
$configFile = Join-Path $TestInstallRoot 'defs\update\update_sources.json'
$productZip = Join-Path $ReleaseDir 'FRBLaunch_0.9.2_PRIVATE_REVIEW_update.zip'
$portableZip = Join-Path $ReleaseDir 'FRBLaunch_0.9.2_PRIVATE_REVIEW_portable.zip'
$productFeed = Join-Path $ReleaseDir 'product_feed.json'
$updaterFeed = Join-Path $ReleaseDir 'updater_feed.json'
$updaterArtifact = Join-Path $ReleaseDir 'FRBUpdater_0.9.3.exe'

foreach ($required in @($stateFile, $configFile, $updaterFeed)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing: $required" }
}
$state = Get-Content -LiteralPath $stateFile -Encoding UTF8 -Raw | ConvertFrom-Json
if (@('0.9.1', '0.9.2') -notcontains [string]$state.version) {
    throw "Unexpected installed integrated version: $($state.version) (expected 0.9.1 or 0.9.2)"
}
$updater = Get-Content -LiteralPath $updaterFeed -Encoding UTF8 -Raw | ConvertFrom-Json
if ($updater.schema -ne 'frb-updater-feed-v1' -or $updater.version -ne '0.9.3') {
    throw 'Updater Feed must already point to version 0.9.3; run stage_FRBUpdater_0.9.3_progress_test.ps1 first.'
}
if (-not (Test-Path -LiteralPath $updaterArtifact -PathType Leaf)) {
    throw "Missing updater artifact: $updaterArtifact"
}
$updaterHash = (Get-FileHash -LiteralPath $updaterArtifact -Algorithm SHA256).Hash.ToLowerInvariant()
if ($updaterHash -ne [string]$updater.sha256) {
    throw 'Updater 0.9.3 feed SHA-256 does not match staged EXE.'
}

$backups = Join-Path (Split-Path -Parent $TestInstallRoot) '.FRBLaunch_update_backups'
if (Test-Path -LiteralPath $backups) {
    foreach ($journalFile in @(Get-ChildItem -LiteralPath $backups -Filter journal.json -File -Recurse -ErrorAction Stop)) {
        try { $journal = Get-Content -LiteralPath $journalFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json }
        catch { throw "Cannot inspect update journal: $($journalFile.FullName)" }
        if ($journal.phase -eq 'applying') { throw "Recovery required before any further update: $($journalFile.FullName)" }
    }
}

if (-not $RefreshConfigOnly) {
    if ($state.version -ne '0.9.1') {
        throw 'Release setup expects the test install to still be at 0.9.1. Use -RefreshConfigOnly after update.'
    }
    foreach ($required in @($python, $launchExe, $updaterExe, $studioExe, $builder)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing: $required" }
    }
    if ((Test-Path -LiteralPath $productZip) -or (Test-Path -LiteralPath $portableZip)) {
        throw "0.9.2 release ZIP already exists; refusing overwrite. Review $ReleaseDir before retrying."
    }
    $appVersionFile = Join-Path $LaunchSource 'src\app_version.py'
    $appVersionText = Get-Content -LiteralPath $appVersionFile -Raw -Encoding UTF8
    $match = [regex]::Match($appVersionText, '(?m)^APP_VERSION\s*=\s*[''"](?<v>\d+\.\d+\.\d+)[''"]')
    if (-not $match.Success) { throw 'Cannot read Launch component version from src/app_version.py' }
    $launchVersion = $match.Groups['v'].Value
    $studioVersion = [string]$state.components.studio
    if ([string]::IsNullOrWhiteSpace($studioVersion)) { throw 'Missing Studio version in installed_release.json' }

    Write-Host '[1/3] Building PRIVATE_REVIEW integrated 0.9.2 release ZIPs...' -ForegroundColor Cyan
    Write-Host "Integrated=0.9.2 / Launch=$launchVersion / Studio=$studioVersion / Updater=0.9.3"
    $argv = @($builder,
        '--launch-source', $LaunchSource,
        '--studio-source', $StudioSource,
        '--output', $ReleaseDir,
        '--version', '0.9.2',
        '--launch-version', $launchVersion,
        '--studio-version', $studioVersion,
        '--updater-version', '0.9.3',
        '--notes', 'Updater 0.9.3 progress-window local test; PRIVATE REVIEW ONLY')
    & $python @argv
    if ($LASTEXITCODE -ne 0) { throw "Release builder failed: $LASTEXITCODE" }
}
if (-not (Test-Path -LiteralPath $productZip -PathType Leaf)) { throw "Missing product ZIP: $productZip" }

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($productZip)
try {
    $entry = $archive.GetEntry('release.json')
    if ($null -eq $entry) { throw 'release.json is missing from update ZIP' }
    $reader = [System.IO.StreamReader]::new($entry.Open(), [Text.Encoding]::UTF8)
    try { $manifest = $reader.ReadToEnd() | ConvertFrom-Json }
    finally { $reader.Dispose() }
} finally { $archive.Dispose() }
if ($manifest.version -ne '0.9.2' -or $manifest.product -ne 'FRBLaunchIntegrated') {
    throw 'Invalid integrated release manifest in 0.9.2 ZIP'
}
if (-not $RefreshConfigOnly) {
    Write-Host '[2/3] Creating new Product Feed for local update...' -ForegroundColor Cyan
    if (Test-Path -LiteralPath $productFeed -PathType Leaf) {
        Copy-Item -LiteralPath $productFeed -Destination ($productFeed + '.before_092_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak') -ErrorAction Stop
    }
    $feed = [ordered]@{
        schema = 'frb-product-feed-v1'
        product = 'FRBLaunchIntegrated'
        version = '0.9.2'
        components = $manifest.components
        notes = 'Updater 0.9.3 progress-window local test; PRIVATE REVIEW ONLY'
        archive_url = 'file:///' + ($productZip -replace '\\', '/')
        size = (Get-Item -LiteralPath $productZip).Length
        sha256 = (Get-FileHash -LiteralPath $productZip -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    [IO.File]::WriteAllText($productFeed, (($feed | ConvertTo-Json -Depth 8) + "`n"), (New-Object Text.UTF8Encoding($false)))
}

Write-Host '[3/3] Configuring local test Feed URLs (with backup)...' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $productFeed -PathType Leaf)) { throw "Missing: $productFeed" }
$product = Get-Content -LiteralPath $productFeed -Raw -Encoding UTF8 | ConvertFrom-Json
if ($product.version -ne '0.9.2') { throw 'Product Feed is not 0.9.2.' }
$backup = $configFile + '.before_092_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak'
Copy-Item -LiteralPath $configFile -Destination $backup -ErrorAction Stop
$sources = [ordered]@{
    schema = 'frb-update-sources-v1'
    updater_feed_url = 'file:///' + ($updaterFeed -replace '\\', '/')
    product_feed_url = 'file:///' + ($productFeed -replace '\\', '/')
    allow_local_for_test = $true
}
[IO.File]::WriteAllText($configFile, (($sources | ConvertTo-Json -Depth 5) + "`n"), (New-Object Text.UTF8Encoding($false)))
Write-Host "[BACKUP] $backup"
Write-Host "[OK] Installed integrated release: $($state.version)" -ForegroundColor Green
Write-Host '[OK] Local updater_feed=0.9.3 / product_feed=0.9.2' -ForegroundColor Green
Write-Host '[SAFE] No product update was started. No backup journals were changed.'
if ($RefreshConfigOnly) {
    Write-Host '[NEXT] Open updated Launch and check latest; it should say version 0.9.2 is current.'
} else {
    Write-Host '[NEXT] From existing 0.9.1 Launch: check latest, verify 0.9.2 + Updater 0.9.3, then click update ONCE.'
    Write-Host '[NOTE] Old Launch will not yet use the new handshake; this test checks the improved Updater 0.9.3 window during apply.'
    Write-Host '[NOTE] After update, use this script with -RefreshConfigOnly if the Feed config was overwritten.'
}
