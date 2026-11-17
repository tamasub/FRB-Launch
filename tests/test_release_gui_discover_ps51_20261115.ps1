# Run on Windows PowerShell 5.1 without GitHub credentials or GUI startup.
# powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_release_gui_discover_ps51_20261115.ps1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$path = Join-Path $root 'release_FRBLaunch_GUI.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw ('GUI PowerShell parse failed: ' + ($errors | Out-String)) }

# Import only pure parsing functions; do not initialize WinForms or execute releases.
foreach ($name in @('Expand-ReleaseRows', 'Get-ReleaseVersions')) {
    $definition = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name }, $true)
    if ($null -eq $definition) { throw ('Missing function: ' + $name) }
    . ([ScriptBlock]::Create($definition.Extent.Text))
}
function Assert-Versions([string]$name, [string]$json, [string[]]$expected) {
    $actual = @(Get-ReleaseVersions $json)
    if ($actual.Count -ne $expected.Count) {
        throw ('FAIL ' + $name + ': expected ' + $expected.Count + ' release(s), got ' + $actual.Count)
    }
    for ($i = 0; $i -lt $actual.Count; $i++) {
        if ($actual[$i] -cne $expected[$i]) {
            throw ('FAIL ' + $name + ': expected ' + $expected[$i] + ', got ' + $actual[$i])
        }
    }
    Write-Host ('PASS ' + $name)
}
Assert-Versions 'empty releases' '[]' @()
Assert-Versions 'one release v0.9.8' '[{"isDraft":false,"tagName":"v0.9.8"}]' @('0.9.8')
Assert-Versions 'multiple releases' '[{"isDraft":false,"tagName":"v0.9.8"},{"isDraft":false,"tagName":"v0.9.7"}]' @('0.9.8','0.9.7')
Assert-Versions 'draft and invalid tags skipped' '[{"isDraft":true,"tagName":"v0.9.9"},{"isDraft":false,"tagName":"wrong"},{"isDraft":false,"tagName":"v0.9.8"}]' @('0.9.8')

# Explicitly reproduce the nested one-element array shape seen in PS5.1.
$inner = New-Object 'object[]' 1
$inner[0] = [pscustomobject]@{ isDraft = $false; tagName = 'v0.9.8' }
$outer = New-Object 'object[]' 1
$outer[0] = $inner
$flat = @(Expand-ReleaseRows $outer)
if ($flat.Count -ne 1 -or $flat[0].tagName -cne 'v0.9.8') {
    throw 'FAIL nested release array normalization'
}
Write-Host 'PASS nested release array normalization'

$threw = $false
try { $null = @(Get-ReleaseVersions '[{"tagName":"v0.9.8"}]') } catch {
    if ($_.Exception.Message -like '*項目が不足しています*') { $threw = $true } else { throw }
}
if (-not $threw) { throw 'FAIL malformed release must be rejected' }
Write-Host 'PASS malformed release rejected'
Write-Host 'ALL PASS (GitHub read-only fixtures; no publish invoked)' -ForegroundColor Green
