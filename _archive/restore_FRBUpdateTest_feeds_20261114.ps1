# FRB Launch - restore LOCAL TEST feed configuration after successful 0.9.1 update.
# Does not run a product update, rebuild executables or touch backup journals.
param(
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$TestInstallRoot = [IO.Path]::GetFullPath($TestInstallRoot).TrimEnd('\')
$ReleaseDir = [IO.Path]::GetFullPath($ReleaseDir).TrimEnd('\')
if ($TestInstallRoot -notmatch '(?i)[\\/]FRB_Update_Test[\\/]FRBLaunch$') {
    throw "Safety guard: only FRB_Update_Test\FRBLaunch may be configured: $TestInstallRoot"
}
$statePath = Join-Path $TestInstallRoot 'installed_release.json'
$configPath = Join-Path $TestInstallRoot 'defs\update\update_sources.json'
$updaterPath = Join-Path $ReleaseDir 'updater_feed.json'
$productPath = Join-Path $ReleaseDir 'product_feed.json'
foreach ($required in @($statePath, $configPath, $updaterPath, $productPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing required file: $required"
    }
}
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
$updater = Get-Content -LiteralPath $updaterPath -Raw -Encoding UTF8 | ConvertFrom-Json
$product = Get-Content -LiteralPath $productPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($state.version -ne '0.9.1') { throw "Expected installed integrated version 0.9.1; got $($state.version)" }
if ($updater.schema -ne 'frb-updater-feed-v1' -or $updater.version -ne '0.9.2') {
    throw "Expected Updater feed 0.9.2: $updaterPath"
}
if ($product.schema -ne 'frb-product-feed-v1' -or $product.version -ne '0.9.1') {
    throw "Expected Product feed 0.9.1: $productPath"
}

$backup = $configPath + '.post_091_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak'
Copy-Item -LiteralPath $configPath -Destination $backup -ErrorAction Stop
$urls = [ordered]@{
    schema = 'frb-update-sources-v1'
    updater_feed_url = 'file:///' + ($updaterPath -replace '\\','/')
    product_feed_url = 'file:///' + ($productPath -replace '\\','/')
    allow_local_for_test = $true
}
$json = ($urls | ConvertTo-Json -Depth 3) + "`n"
[IO.File]::WriteAllText($configPath, $json, (New-Object Text.UTF8Encoding($false)))
$readBack = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($readBack.updater_feed_url -ne $urls.updater_feed_url -or
    $readBack.product_feed_url -ne $urls.product_feed_url -or
    -not $readBack.allow_local_for_test) {
    throw 'Failed to verify update_sources.json after writing'
}
Write-Host '[OK] Installed integrated release: 0.9.1' -ForegroundColor Green
Write-Host '[OK] Feed source config restored for LOCAL TEST only.' -ForegroundColor Green
Write-Host "[BACKUP] $backup"
Write-Host "[CONFIG] $configPath"
Write-Host '[NEXT] Open Launch > Version update information > Check latest.'
Write-Host '[EXPECTED] Latest installed, so update start button should stay disabled.'
Write-Host '[NOTE] A future system update may overwrite this setting again until code is fixed.'
