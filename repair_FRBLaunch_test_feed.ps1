# ローカル更新試験のURLを System と UserConfig の両方に設定。
# Launch／Studioを完全に終了してから実行する。Updater本体は起動しない。
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
    if (-not $python) { $python = (Get-Command python -ErrorAction Stop).Source }
}
$script = Join-Path $PSScriptRoot 'scripts\repair_update_test_feed_sources.py'
$argsList = @($script)
if ($DryRun) { $argsList += '--dry-run' }
& $python @argsList
if ($LASTEXITCODE -ne 0) { throw "ローカルFeed修復が失敗しました (exit=$LASTEXITCODE)" }
