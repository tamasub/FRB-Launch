# FRB Updater v0.9.2 - local test feed preparation (NOT update execution)
# Only stages the freshly built Updater, verifies the 0.9.1 product ZIP,
# and writes local test feeds. Optional: configure the test installation.
param(
    [string]$LaunchSource = 'F:\FRB_Apps\FRB_Launch',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$ConfigureTestInstall
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$LaunchSource = [System.IO.Path]::GetFullPath($LaunchSource)
$ReleaseDir = [System.IO.Path]::GetFullPath($ReleaseDir)
$TestInstallRoot = [System.IO.Path]::GetFullPath($TestInstallRoot)
$python = Join-Path $LaunchSource '.venv\Scripts\python.exe'
$build = Join-Path $LaunchSource '_build_updater_windows.bat'
$verifier = Join-Path $LaunchSource 'scripts\verify_updater_binary.py'
$builtExe = Join-Path $LaunchSource 'dist\updater\FRBUpdater.exe'
$stagedExe = Join-Path $ReleaseDir 'FRBUpdater_0.9.2.exe'
$productZip = Join-Path $ReleaseDir 'FRBLaunch_0.9.1_PRIVATE_REVIEW_update.zip'

foreach ($file in @($python, $build, $verifier, $productZip)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Missing prerequisite: $file"
    }
}
Write-Host '[1/4] Build standalone Updater without Tcl/Tk...' -ForegroundColor Cyan
Push-Location $LaunchSource
try {
    & $build
    if ($LASTEXITCODE -ne 0) { throw "Updater build failed (exit=$LASTEXITCODE)" }
    & $python $verifier $builtExe
    if ($LASTEXITCODE -ne 0) { throw "Updater Tk-free archive check failed (exit=$LASTEXITCODE)" }
} finally {
    Pop-Location
}

Write-Host '[2/4] Stage FRBUpdater_0.9.2.exe without overwriting older releases...' -ForegroundColor Cyan
$sourceHash = (Get-FileHash -LiteralPath $builtExe -Algorithm SHA256).Hash
if (Test-Path -LiteralPath $stagedExe -PathType Leaf) {
    $existingHash = (Get-FileHash -LiteralPath $stagedExe -Algorithm SHA256).Hash
    if ($existingHash -ne $sourceHash) {
        throw "v0.9.2 artifact exists but has different SHA256: $stagedExe. Choose another version; do not silently overwrite it."
    }
    Write-Host '[OK] Matching staged v0.9.2 executable already exists.'
} else {
    Copy-Item -LiteralPath $builtExe -Destination $stagedExe -ErrorAction Stop
}

Write-Host '[3/4] Verify product ZIP and generate local test Feed JSON files...' -ForegroundColor Cyan
# Python stdin script: read release.json from the product ZIP; verify full archive;
# compute SHA256/size from actual bytes; create file:/// URLs on Windows.
$feedScript = @'
import hashlib, json, sys, zipfile
from pathlib import Path
launch = Path(sys.argv[1]); release = Path(sys.argv[2]); exe = Path(sys.argv[3]); product = Path(sys.argv[4])
sys.path.insert(0, str(launch / 'src'))
from frb_update.updater_core import validate_zip

def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()

def save_feed(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if path.exists():
        old = path.with_name(path.name + '.before_0.9.2.bak')
        if not old.exists():
            old.write_bytes(path.read_bytes())
        print('[BACKUP]', old)
    path.write_bytes(data)
    print('[FEED]', path)

manifest = validate_zip(product, expected_version='0.9.1')
components = manifest.get('components')
if not isinstance(components, dict) or set(components) != {'launch','studio'}:
    raise ValueError('Bad components in product release.json')
updater_feed = {
    'schema': 'frb-updater-feed-v1', 'version': '0.9.2',
    'url': exe.resolve().as_uri(), 'size': exe.stat().st_size,
    'sha256': hash_file(exe),
}
product_feed = {
    'schema': 'frb-product-feed-v1', 'product': 'FRBLaunchIntegrated',
    'version': manifest['version'], 'components': components,
    'notes': manifest.get('notes') or '0.9.1 local update retest with Updater 0.9.2',
    'archive_url': product.resolve().as_uri(), 'size': product.stat().st_size,
    'sha256': hash_file(product),
}
save_feed(release / 'updater_feed.json', updater_feed)
save_feed(release / 'product_feed.json', product_feed)
'@
$feedScript | & $python - $LaunchSource $ReleaseDir $stagedExe $productZip
if ($LASTEXITCODE -ne 0) { throw "Feed preparation failed (exit=$LASTEXITCODE)" }

if ($ConfigureTestInstall) {
    Write-Host '[4/4] Configure only the explicit FRB_Update_Test installation...' -ForegroundColor Cyan
    if ($TestInstallRoot -notmatch '(?i)[\\/]FRB_Update_Test[\\/]FRBLaunch$') {
        throw "Refusing to edit a non-test installation: $TestInstallRoot"
    }
    $sources = Join-Path $TestInstallRoot 'defs\update\update_sources.json'
    if (-not (Test-Path -LiteralPath $sources -PathType Leaf)) {
        throw "Test install sources missing: $sources"
    }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    Copy-Item -LiteralPath $sources -Destination ($sources + '.before_local_test_' + $stamp + '.bak') -ErrorAction Stop
    $uriUpdater = ([System.IO.Path]::GetFullPath((Join-Path $ReleaseDir 'updater_feed.json')) -replace '\\', '/')
    $uriProduct = ([System.IO.Path]::GetFullPath((Join-Path $ReleaseDir 'product_feed.json')) -replace '\\', '/')
    $config = [ordered]@{
        schema = 'frb-update-sources-v1'
        updater_feed_url = 'file:///' + $uriUpdater
        product_feed_url = 'file:///' + $uriProduct
        allow_local_for_test = $true
    }
    # UTF-8 sans BOM: compatible with both Windows PowerShell and the app.
    $data = ($config | ConvertTo-Json -Depth 4) + "`n"
    [System.IO.File]::WriteAllText($sources, $data, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "[OK] Test sources configured: $sources" -ForegroundColor Green
} else {
    Write-Host '[4/4] Test installation untouched (use -ConfigureTestInstall to configure local Feed URLs).'
}
Write-Host ''
Write-Host '[READY] Local updater feed is v0.9.2 and product feed is v0.9.1.' -ForegroundColor Green
Write-Host '[SAFE] No update was started. Original v0.9.0/v0.9.1 EXEs and ZIPs were not modified.'
Write-Host '[NEXT] Start the restored test Launch, check latest version, then explicitly choose update.'
