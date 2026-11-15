# FRB Launch: ZIP作成メニューの旧実行先をソースRootへ戻す。
# Launch/Studioを終了して実行すること。UserDataはバックアップ後に原子的に更新。
# Expに旧変数が残っていれば同じ限定修復対象として扱う。
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
    if (-not $python) { $python = (Get-Command python -ErrorAction Stop).Source }
}
$argsList = @((Join-Path $PSScriptRoot 'scripts\repair_exp_development_roots.py'))
if ($DryRun) { $argsList += '--dry-run' }
& $python @argsList
if ($LASTEXITCODE -ne 0) { throw "ZIP登録先修復に失敗しました (exit=$LASTEXITCODE)" }
