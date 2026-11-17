# FRB Launch missing Python modules recovery (2026-11-17, path argument fix).
# Extract this bundle in the FRB_Launch root and run its BAT.
# NEVER overwrite existing files in src.
$ErrorActionPreference = 'Stop'

# No path arguments needed. $PSScriptRoot is the absolute location of this script.
$LaunchRoot = $PSScriptRoot
$source = Join-Path $LaunchRoot 'restore_payload\src'
$target = Join-Path $LaunchRoot 'src'

if (-not (Test-Path -LiteralPath (Join-Path $target 'app.py') -PathType Leaf)) {
    Write-Host 'ERROR: src\app.py was not found. Extract the full ZIP into the FRB_Launch folder.' -ForegroundColor Red
    exit 2
}
if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    Write-Host 'ERROR: restore_payload\src is missing. Extract the full ZIP first.' -ForegroundColor Red
    exit 2
}
foreach ($required in @('remote_confirmation.py','dialog_button_selection.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $source $required) -PathType Leaf)) {
        Write-Host ('ERROR: bundle is missing ' + $required) -ForegroundColor Red
        exit 2
    }
}

# Keep SHA-256 checksums of existing modules to prove that existing code is untouched.
$guard = @{}
$files = @(Get-ChildItem -LiteralPath $source -Recurse -File -Filter '*.py')
foreach ($file in @(Get-ChildItem -LiteralPath $target -Recurse -File -Filter '*.py')) {
    $guard[$file.FullName] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
}

$copied = New-Object 'System.Collections.Generic.List[string]'
$kept = 0
foreach ($file in $files) {
    $rel = $file.FullName.Substring($source.Length + 1)
    $dest = Join-Path $target $rel
    if (Test-Path -LiteralPath $dest) {
        $kept++
        continue
    }
    $destDir = Split-Path -Parent $dest
    if (-not (Test-Path -LiteralPath $destDir -PathType Container)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    # Do not overwrite, even when a race creates a file between the checks.
    if (-not (Test-Path -LiteralPath $dest)) {
        Copy-Item -LiteralPath $file.FullName -Destination $dest -ErrorAction Stop
        $copied.Add($rel)
    } else {
        $kept++
    }
}

foreach ($path in $guard.Keys) {
    $current = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($current -ne $guard[$path]) {
        Write-Host ('ERROR: Existing file was changed: ' + $path) -ForegroundColor Red
        exit 3
    }
}
$missing = @()
foreach ($file in $files) {
    $rel = $file.FullName.Substring($source.Length + 1)
    if (-not (Test-Path -LiteralPath (Join-Path $target $rel) -PathType Leaf)) {
        $missing += $rel
    }
}
Write-Host ''
Write-Host 'FRB Launch: missing source module recovery' -ForegroundColor Cyan
Write-Host ('Target: ' + $LaunchRoot)
Write-Host ('Included modules: ' + $files.Count)
Write-Host ('Restored missing: ' + $copied.Count)
Write-Host ('Existing files preserved: ' + $kept)
foreach ($rel in $copied) { Write-Host ('  restored src\' + $rel) }
if ($missing.Count -gt 0) {
    Write-Host ('ERROR: Missing files remain: ' + $missing.Count) -ForegroundColor Red
    exit 4
}
Write-Host 'PASS: Existing source unchanged; all reference Python modules are present.' -ForegroundColor Green
Write-Host 'Restart FRB Launch normally.' -ForegroundColor Green
exit 0
