[CmdletBinding()]
param(
    [Parameter(Position=0)] [string] $Root = '.',
    [switch] $GitDiff,
    [string[]] $Extensions = @('.py','.pyw','.js','.mjs','.cjs','.ts','.tsx','.jsx','.cs','.html','.htm','.css','.scss','.ps1','.psm1','.bat','.cmd','.ahk','.c','.cpp','.h','.hpp','.ino','.java','.go','.rs','.vb','.xaml','.sh','.sql'),
    [string[]] $ExcludeDirs = @('.git','.svn','.hg','node_modules','__pycache__','.venv','venv','.tox','.pytest_cache','.mypy_cache','bin','obj','build','dist','out','vendor','packages','.vs','coverage','99_test_runtime')
)
$ErrorActionPreference = 'Stop'
$rootItem = Get-Item -LiteralPath $Root -Force
if (-not $rootItem.PSIsContainer -or $rootItem.PSProvider.Name -ne 'FileSystem') { throw "Not a filesystem directory: $Root" }
$rootPath = $rootItem.FullName
$prefix = $rootPath.TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
$extSet = @{}
foreach ($ext in $Extensions) { $extSet['.' + $ext.TrimStart('.').ToLowerInvariant()] = $true }
$skipSet = @{}
foreach ($dir in $ExcludeDirs) { $skipSet[$dir] = $true }
$ownFiles = @($PSCommandPath, [IO.Path]::ChangeExtension($PSCommandPath, '.bat'))
$rows = New-Object 'System.Collections.Generic.List[object]'
$dirs = New-Object 'System.Collections.Generic.Stack[string]'
$dirs.Push($rootPath)
while ($dirs.Count -gt 0) {
    $dir = $dirs.Pop()
    foreach ($item in (Get-ChildItem -LiteralPath $dir -Force -ErrorAction Stop)) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        if ($item.PSIsContainer) {
            if (-not $skipSet.ContainsKey($item.Name)) { $dirs.Push($item.FullName) }
            continue
        }
        $ext = $item.Extension.ToLowerInvariant()
        if (-not $extSet.ContainsKey($ext) -or $ownFiles -contains $item.FullName) { continue }
        [long]$total = 0
        [long]$nonBlank = 0
        foreach ($line in [IO.File]::ReadLines($item.FullName)) {
            $total++
            if (-not [string]::IsNullOrWhiteSpace($line)) { $nonBlank++ }
        }
        $rows.Add([pscustomobject]@{
            File = $item.FullName.Substring($prefix.Length)
            Ext = $ext
            Lines = $total
            Blank = $total - $nonBlank
            NonBlank = $nonBlank
        })
    }
}
Write-Host "`n=== SOURCE STEPS ===" -ForegroundColor Cyan
Write-Host "Root: $rootPath"
Write-Host ('Extensions: ' + (($extSet.Keys | Sort-Object) -join ', '))
Write-Host ('Excluded directories: ' + (($skipSet.Keys | Sort-Object) -join ', '))
Write-Host "`n--- By file (largest first) ---"
$rows | Sort-Object -Property @{Expression='Lines';Descending=$true}, File | Format-Table File, Lines, Blank, NonBlank -AutoSize -Wrap
Write-Host "`n--- By extension ---"
$rows | Group-Object Ext | ForEach-Object {
    [pscustomobject]@{
        Extension = $_.Name
        Files = $_.Count
        Lines = ($_.Group | Measure-Object Lines -Sum).Sum
        Blank = ($_.Group | Measure-Object Blank -Sum).Sum
        NonBlank = ($_.Group | Measure-Object NonBlank -Sum).Sum
    }
} | Sort-Object Lines -Descending | Format-Table -AutoSize
[long]$all = ($rows | Measure-Object Lines -Sum).Sum
[long]$blank = ($rows | Measure-Object Blank -Sum).Sum
Write-Host ('TOTAL: {0:N0} files / {1:N0} lines / {2:N0} non-blank / {3:N0} blank' -f $rows.Count,$all,($all-$blank),$blank) -ForegroundColor Green

if ($GitDiff) {
    Write-Host "`n--- Git changes against HEAD (tracked files only) ---" -ForegroundColor Cyan
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Write-Warning 'Git is not installed.'; return }
    Push-Location -LiteralPath $rootPath
    $oldEncoding = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        & git rev-parse --verify HEAD 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning 'No Git HEAD available.'; return }
        $changes = & git -c core.quotepath=false diff --no-renames --no-ext-diff --no-textconv --numstat --relative HEAD -- .
        if ($LASTEXITCODE -ne 0) { throw 'git diff failed.' }
        $diffRows = @($changes | ForEach-Object {
            if ($_ -match '^([0-9]+)\t([0-9]+)\t(.+)$') {
                $added = [long]$Matches[1]; $deleted = [long]$Matches[2]; $file = $Matches[3]
                $parts = $file -split '/'
                $excluded = $false
                for ($i = 0; $i -lt $parts.Count - 1; $i++) { if ($skipSet.ContainsKey($parts[$i])) { $excluded = $true; break } }
                if (-not $excluded -and $extSet.ContainsKey([IO.Path]::GetExtension($file).ToLowerInvariant()) -and $ownFiles -notcontains (Join-Path $rootPath $file)) {
                    [pscustomobject]@{ File=$file; Added=$added; Deleted=$deleted; Delta=($added-$deleted) }
                }
            }
        })
        if ($diffRows.Count -eq 0) { Write-Host '(No matching text changes)' }
        else { $diffRows | Sort-Object Delta -Descending | Format-Table -AutoSize -Wrap }
        [long]$add = ($diffRows | Measure-Object Added -Sum).Sum
        [long]$del = ($diffRows | Measure-Object Deleted -Sum).Sum
        Write-Host ('GIT TOTAL: +{0:N0} / -{1:N0} / delta {2:N0}' -f $add,$del,($add-$del))
        Write-Host 'Untracked files and binary diffs are not included in Git changes.'
    } finally {
        [Console]::OutputEncoding = $oldEncoding
        Pop-Location
    }
}
