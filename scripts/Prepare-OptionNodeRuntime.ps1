# Bundle official Node.js Windows node.exe with the integrated FRB Launch release.
# Source must be a trusted official Node.js distribution with its LICENSE file.
param(
  [Parameter(Mandatory=$true)][string]$NodeExecutable,
  [Parameter(Mandatory=$true)][string]$NodeLicenseFile
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$destination = Join-Path $root 'runtime\node'
$node = (Resolve-Path -LiteralPath $NodeExecutable).Path
$license = (Resolve-Path -LiteralPath $NodeLicenseFile).Path
if ([System.IO.Path]::GetFileName($node) -ine 'node.exe') {
  throw 'Expected the trusted official Node.js node.exe.'
}
if ([System.IO.Path]::GetFileName($license) -ine 'LICENSE') {
  throw 'Expected the matching Node.js LICENSE file.'
}
if (Test-Path -LiteralPath (Join-Path $destination 'node.exe')) {
  throw 'Refusing to silently overwrite an existing packaged node.exe.'
}
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -LiteralPath $node -Destination (Join-Path $destination 'node.exe')
Copy-Item -LiteralPath $license -Destination (Join-Path $destination 'NODE_LICENSE.txt')
Write-Host ('[OK] Portable Node runtime: ' + $destination)
Write-Host '[INFO] Integrate runtime/node into the release ZIP alongside Studio tools/option_settings.'
