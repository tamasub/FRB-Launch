# PRIVATE REVIEW ONLY: integrate Launch 0.9.2 + Studio 0.9.0 + Updater 0.9.4.
# Runs on Windows PowerShell 5.1; creates no installed-product update automatically.
param(
    [string]$LaunchSource = 'F:\FRB_Apps\FRB_Launch',
    [string]$StudioSource = 'F:\FRB_Apps\FRB_Studio',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$ResumeAfterBuild,
    [switch]$RefreshConfigOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($ResumeAfterBuild -and $RefreshConfigOnly) {
    throw 'Choose -ResumeAfterBuild OR -RefreshConfigOnly.'
}
$LaunchSource = [IO.Path]::GetFullPath($LaunchSource)
$StudioSource = [IO.Path]::GetFullPath($StudioSource)
$ReleaseDir = [IO.Path]::GetFullPath($ReleaseDir)
$TestInstallRoot = [IO.Path]::GetFullPath($TestInstallRoot)
$python = Join-Path $LaunchSource '.venv\Scripts\python.exe'
$helper = Join-Path $LaunchSource 'scripts\prepare_FRBLaunch_094_test_feeds.py'
$builder = Join-Path $LaunchSource 'scripts\build_portable_distribution.py'
$buildUpdater = Join-Path $LaunchSource '_build_updater_windows.bat'
$updateZip = Join-Path $ReleaseDir 'FRBLaunch_0.9.4_PRIVATE_REVIEW_update.zip'
$portableZip = Join-Path $ReleaseDir 'FRBLaunch_0.9.4_PRIVATE_REVIEW_portable.zip'
foreach ($file in @($python, $helper)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing: $file" }
}
$common = @('--launch-source', $LaunchSource, '--studio-source', $StudioSource,
    '--release-dir', $ReleaseDir, '--install-root', $TestInstallRoot)
if ($RefreshConfigOnly) {
    Write-Host '[REFRESH] Restore only local TEST Feed config, no build' -ForegroundColor Cyan
    & $python $helper --phase refresh @common
    if ($LASTEXITCODE -ne 0) { throw 'Feed config refresh failed.' }
    exit 0
}

if (-not $ResumeAfterBuild -and ((Test-Path -LiteralPath $updateZip) -or (Test-Path -LiteralPath $portableZip))) {
    throw '0.9.4 ZIP already exists; use -ResumeAfterBuild to verify and continue without overwriting.'
}
if (-not $ResumeAfterBuild) {
    if (-not (Test-Path -LiteralPath $buildUpdater -PathType Leaf)) { throw "Missing: $buildUpdater" }
    if (-not (Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Missing: $builder" }
    Write-Host '[1/3] Rebuild Updater (native progress) and verify built binaries...' -ForegroundColor Cyan
    Push-Location $LaunchSource
    try {
        & $buildUpdater
        if ($LASTEXITCODE -ne 0) { throw "Updater build failed: $LASTEXITCODE" }
    } finally { Pop-Location }
    & $python $helper --phase preflight @common
    if ($LASTEXITCODE -ne 0) { throw 'Built-binary preflight failed. Launch rebuild needed?' }
    Write-Host '[2/3] Create immutable PRIVATE_REVIEW integrated 0.9.4 ZIPs...' -ForegroundColor Cyan
    $argsList = @($builder, '--launch-source', $LaunchSource,
        '--studio-source', $StudioSource, '--output', $ReleaseDir,
        '--version', '0.9.4', '--launch-version', '0.9.2',
        '--studio-version', '0.9.0', '--updater-version', '0.9.4',
        '--notes', 'Exp roots / Studio editor / persisted Feed / 100% progress; PRIVATE REVIEW ONLY')
    & $python @argsList
    if ($LASTEXITCODE -ne 0) { throw "Integrated builder failed: $LASTEXITCODE" }
} else {
    Write-Host '[1-2/3] Reuse existing immutable 0.9.4 ZIPs; do not rebuild' -ForegroundColor Cyan
    foreach ($file in @($updateZip, $portableZip)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Resume requires: $file" }
    }
}
Write-Host '[3/3] Verify ZIPs, stage 0.9.4 Feeds and configure TEST install...' -ForegroundColor Cyan
& $python $helper --phase stage @common
if ($LASTEXITCODE -ne 0) { throw '0.9.4 Feed staging failed.' }
Write-Host '[OK] 0.9.4 product Feed / Updater Feed / test config prepared.' -ForegroundColor Green
Write-Host '[SAFE] Update not started. 0.9.3 installed System/Journal untouched.' -ForegroundColor Green
