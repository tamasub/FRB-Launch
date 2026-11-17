$ErrorActionPreference = 'Stop'
# No root-path argument: avoid a quoted trailing backslash mishap.
$root = $PSScriptRoot
$files = @(
  'src/app.py',
  'src/expanded_view.py',
  'src/studio_preview_panel.py',
  'tests/test_sakura_explicit_popout_contract_20261117.py',
  'tests/test_external_editor_focus_close_v2_20261117.py',
  'tests/test_sakura_focus_and_clean_close_20261117.py',
  'tests/test_sakura_owned_window_safety_20261117.py',
  'tests/test_external_editors_multifile_safe_20261117.py',
  'tests/test_studio_third_column_settings_and_close_20261117.py'
)
foreach ($required in @('src/app.py', 'src/expanded_view.py', 'src/studio_preview_panel.py')) {
  if (-not (Test-Path -LiteralPath (Join-Path $root $required) -PathType Leaf)) {
    throw "STOP: this must run from the FRB Launch project root. Missing: $required"
  }
}
foreach ($file in $files) {
  if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $root 'patch') $file) -PathType Leaf)) {
    throw "STOP: patch file missing: $file"
  }
}
$backup = Join-Path $root ('backups\sakura_popout_before_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach ($file in $files) {
  $from = Join-Path (Join-Path $root 'patch') $file
  $to = Join-Path $root $file
  $saved = Join-Path $backup $file
  if (Test-Path -LiteralPath $to -PathType Leaf) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
    Copy-Item -LiteralPath $to -Destination $saved -Force
  }
}
foreach ($file in $files) {
  $from = Join-Path (Join-Path $root 'patch') $file
  $to = Join-Path $root $file
  New-Item -ItemType Directory -Path (Split-Path -Parent $to) -Force | Out-Null
  Copy-Item -LiteralPath $from -Destination $to -Force
  Write-Host "UPDATED: $file"
}
Write-Host "PASS: patch applied. Backup: $backup"
