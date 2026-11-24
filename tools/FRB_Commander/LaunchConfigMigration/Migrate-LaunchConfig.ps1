param(
    [Parameter(Mandatory=$true)][ValidateSet('Preview','Convert')][string]$Mode,
    [string]$InputJson
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
try {
    $root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
    $candidates = @((Join-Path $root 'runtime\node\node.exe'), (Join-Path $root 'Studio\runtime\node\node.exe'))
    # Portable distributions never fall back to a machine-wide Node installation.
    $portable = (Test-Path -LiteralPath (Join-Path $root 'installed_release.json')) -or (Test-Path -LiteralPath (Join-Path $root 'FRBLaunch.exe'))
    if (-not $portable) {
        $sibling = Join-Path (Split-Path -Parent $root) 'FRB_Studio'
        $candidates += @((Join-Path $sibling 'runtime\node\node.exe'), (Join-Path $sibling 'node.exe'))
    }
    $node = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $node -and -not $portable) { $cmd = Get-Command node.exe -ErrorAction SilentlyContinue; if ($cmd) { $node = $cmd.Source } }
    if (-not $node) { throw 'Bundled Node.js not found (runtime/node/node.exe or Studio/runtime/node/node.exe).' }
    if (-not $InputJson) {
        if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is not set.' }
        $InputJson = Join-Path $env:LOCALAPPDATA 'FRBLaunch\UserData\frb_launch_data.json'
    }
    if (-not (Test-Path -LiteralPath $InputJson -PathType Leaf)) { throw "Launch user JSON not found: $InputJson" }
    $inputPath = (Resolve-Path -LiteralPath $InputJson).Path
    & $node (Join-Path $PSScriptRoot 'migrate-launch-config.mjs') $Mode $inputPath (Join-Path $root 'config\expanded_view_options.json')
    exit $LASTEXITCODE
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
