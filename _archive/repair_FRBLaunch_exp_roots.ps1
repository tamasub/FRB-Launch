# LaunchとStudioを閉じてから実行。UpdaterのSystemやJournalは変更しません。
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
    if (-not $python) { $python = (Get-Command python -ErrorAction Stop).Source }
}
$script = Join-Path $PSScriptRoot 'scripts\repair_exp_development_roots.py'
$argsList = @($script)
if ($DryRun) { $argsList += '--dry-run' }
& $python @argsList
if ($LASTEXITCODE -ne 0) { throw "Exp修復が失敗しました (exit=$LASTEXITCODE)" }
