# Stage only a newly built FRB Updater 0.9.3 for LOCAL TEST.
# Does NOT change Product Feed, install product ZIP, or run an update.
param(
    [string]$LaunchSource = 'F:\FRB_Apps\FRB_Launch',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$ConfigureTestInstall
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$LaunchSource = [IO.Path]::GetFullPath($LaunchSource)
$ReleaseDir = [IO.Path]::GetFullPath($ReleaseDir)
$TestInstallRoot = [IO.Path]::GetFullPath($TestInstallRoot)
$python = Join-Path $LaunchSource '.venv\Scripts\python.exe'
$build = Join-Path $LaunchSource '_build_updater_windows.bat'
$verifier = Join-Path $LaunchSource 'scripts\verify_updater_binary.py'
$built = Join-Path $LaunchSource 'dist\updater\FRBUpdater.exe'
$staged = Join-Path $ReleaseDir 'FRBUpdater_0.9.3.exe'
$updaterFeed = Join-Path $ReleaseDir 'updater_feed.json'
$productFeed = Join-Path $ReleaseDir 'product_feed.json'
foreach ($required in @($python, $build, $verifier, $productFeed)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing: $required" }
}
Write-Host '[1/3] Build and validate native Updater...' -ForegroundColor Cyan
Push-Location $LaunchSource
try {
    & $build
    if ($LASTEXITCODE -ne 0) { throw 'Updater build failed.' }
    & $python $verifier $built
    if ($LASTEXITCODE -ne 0) { throw 'Updater binary validation failed.' }
} finally { Pop-Location }

Write-Host '[2/3] Stage NEW immutable 0.9.3 artifact...' -ForegroundColor Cyan
$newHash = (Get-FileHash -LiteralPath $built -Algorithm SHA256).Hash
if (Test-Path -LiteralPath $staged -PathType Leaf) {
    $oldHash = (Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash
    if ($newHash -ne $oldHash) { throw "0.9.3 already exists with other bytes. Refusing overwrite: $staged" }
} else {
    Copy-Item -LiteralPath $built -Destination $staged -ErrorAction Stop
}
$record = [ordered]@{
    schema = 'frb-updater-feed-v1'
    version = '0.9.3'
    url = ([Uri]$staged).AbsoluteUri
    size = (Get-Item -LiteralPath $staged).Length
    sha256 = $newHash.ToLowerInvariant()
}
if (Test-Path -LiteralPath $updaterFeed -PathType Leaf) {
    $backup = $updaterFeed + '.before_093_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak'
    Copy-Item -LiteralPath $updaterFeed -Destination $backup
    Write-Host "[BACKUP] $backup"
}
[IO.File]::WriteAllText($updaterFeed, ($record | ConvertTo-Json -Depth 5) + "`n", (New-Object Text.UTF8Encoding($false)))
if ($ConfigureTestInstall) {
    if ($TestInstallRoot -notmatch '(?i)[\\/]FRB_Update_Test[\\/]FRBLaunch$') {
        throw "Safety guard: not a test installation: $TestInstallRoot"
    }
    $configPath = Join-Path $TestInstallRoot 'defs\update\update_sources.json'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { throw "Missing: $configPath" }
    $backup = $configPath + '.before_093_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak'
    Copy-Item -LiteralPath $configPath -Destination $backup
    $sources = [ordered]@{
        schema = 'frb-update-sources-v1'
        updater_feed_url = ([Uri]$updaterFeed).AbsoluteUri
        product_feed_url = ([Uri]$productFeed).AbsoluteUri
        allow_local_for_test = $true
    }
    [IO.File]::WriteAllText($configPath, ($sources | ConvertTo-Json -Depth 5) + "`n", (New-Object Text.UTF8Encoding($false)))
    Write-Host "[CONFIG] $configPath" -ForegroundColor Green
}
Write-Host '[3/3] Safe UI smoke test (no installation changes)...' -ForegroundColor Cyan
Write-Host "Run: & '$built' ui-test --show-progress"
Write-Host '[NOTE] Product Feed was left untouched. Already-installed 0.9.1 cannot be updated to 0.9.1 again.'
Write-Host '[NOTE] Full Launch-side handshake requires a NEW integrated product release containing the patched Launch EXE.'
Write-Host '[OK] Updater 0.9.3 staged. No update was launched.' -ForegroundColor Green
