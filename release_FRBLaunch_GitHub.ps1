# FRB Launch release after manual _build_windows.bat.
# Windows PowerShell 5.1, ASCII source and CRLF.
# No automatic update of user installations. Remote publish requires exact tag confirmation.
param(
    [Parameter(Mandatory=$true)][string]$Version,
    [string]$Repo = 'tamasub/FRB-Launch',
    [string]$ChannelBranch = 'main',
    [string]$StudioVersion = '0.9.0',
    [string]$UpdaterVersion = '',
    [string]$Notes = 'FRB Launch usability and updater improvements',
    [string]$LaunchSource = '',
    [string]$StudioSource = 'F:\FRB_Apps\FRB_Studio',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$PrepareOnly,
    [switch]$PublishOnly,
    [switch]$ConfigureTestInstall,
    [switch]$SkipUpdaterBuild,
    [string]$GuiApprovedTag = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
# Resolve the source root AFTER param binding. In Windows PowerShell 5.1,
# an automatic variable may be empty in a parameter default expression.
if ([string]::IsNullOrWhiteSpace($LaunchSource)) {
    $entryPath = $MyInvocation.MyCommand.Path
    if ([string]::IsNullOrWhiteSpace($entryPath)) {
        throw 'Cannot determine script location. Pass -LaunchSource explicitly.'
    }
    $LaunchSource = Split-Path -Path $entryPath -Parent
}
if ([string]::IsNullOrWhiteSpace($LaunchSource)) {
    throw 'LaunchSource is empty. Specify -LaunchSource with the source directory.'
}
if (-not (Test-Path -LiteralPath $LaunchSource -PathType Container)) {
    throw "LaunchSource folder does not exist: $LaunchSource"
}
$LaunchSource = (Resolve-Path -LiteralPath $LaunchSource).ProviderPath
Write-Host ("[ROOT] Launch source: {0}" -f $LaunchSource)
$selectedModeCount = 0
foreach ($mode in @($PrepareOnly, $PublishOnly, $ConfigureTestInstall)) {
    if ($mode) { $selectedModeCount++ }
}
if ($selectedModeCount -gt 1) {
    throw 'Use only one mode switch: PrepareOnly, PublishOnly, ConfigureTestInstall.'
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Specify -Version x.y.z' }
if (-not $UpdaterVersion) { $UpdaterVersion = $Version }
$python = Join-Path $LaunchSource '.venv\Scripts\python.exe'
$helper = Join-Path $LaunchSource 'scripts\release_github_pipeline.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python venv missing: $python" }
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw "Release pipeline helper missing: $helper" }
$argsCommon = @(
    '--version', $Version,
    '--repo', $Repo,
    '--channel-branch', $ChannelBranch,
    '--studio-version', $StudioVersion,
    '--updater-version', $UpdaterVersion,
    '--notes', $Notes,
    '--launch-source', $LaunchSource,
    '--studio-source', $StudioSource,
    '--release-dir', $ReleaseDir,
    '--test-install', $TestInstallRoot
)
function Invoke-ReleaseStep([string]$Action, [string[]]$ExtraArgs) {
    & $python $helper $Action @argsCommon @ExtraArgs
    if ($LASTEXITCODE -ne 0) { throw "Release step '$Action' failed (exit $LASTEXITCODE)" }
}
if ($ConfigureTestInstall) {
    Invoke-ReleaseStep 'configure-test' @()
    Write-Host '[SAFE] TEST Feed only. No update was executed.' -ForegroundColor Green
    exit 0
}
if (-not $PublishOnly) {
    if (-not $SkipUpdaterBuild) {
        $updaterExe = Join-Path $LaunchSource 'dist\updater\FRBUpdater.exe'
        $updaterInputSources = @(
            'src\frb_updater_main.py',
            'src\frb_update\updater_core.py',
            'src\frb_update\progress_ui.py',
            'src\frb_update\progress_gate.py',
            'src\frb_update\contracts.py'
        )
        $needBuild = -not (Test-Path -LiteralPath $updaterExe -PathType Leaf)
        if (-not $needBuild) {
            foreach ($relative in $updaterInputSources) {
                $file = Join-Path $LaunchSource $relative
                if ((Test-Path -LiteralPath $file -PathType Leaf) -and
                    ((Get-Item -LiteralPath $file).LastWriteTimeUtc -gt (Get-Item -LiteralPath $updaterExe).LastWriteTimeUtc)) {
                    $needBuild = $true
                    break
                }
            }
        }
        if ($needBuild) {
            Write-Host '[BUILD] Updater source is newer; rebuild standalone Updater...' -ForegroundColor Cyan
            $build = Join-Path $LaunchSource '_build_updater_windows.bat'
            if (-not (Test-Path -LiteralPath $build -PathType Leaf)) { throw "Missing updater build command: $build" }
            & cmd.exe /d /c ('"' + $build + '"')
            if ($LASTEXITCODE -ne 0) { throw 'Updater build failed' }
        } else {
            Write-Host '[REUSE] Existing Updater EXE is newer than its source.' -ForegroundColor Cyan
        }
    }
    Invoke-ReleaseStep 'stage' @()
}
Invoke-ReleaseStep 'verify' @()
$tag = 'v' + $Version
$stage = Join-Path $ReleaseDir ('github_' + $Version)
Write-Host ''
Write-Host '------------------------------------------------------'
Write-Host '  FRB Launch release preflight OK' -ForegroundColor Green
Write-Host ("  Repository: {0}" -f $Repo)
Write-Host ("  Release tag: {0}" -f $tag)
Write-Host ("  Staged files: {0}" -f $stage)
Write-Host '  GitHub publish: NOT YET EXECUTED'
Write-Host '  Preview channel: release-feed/preview (fixed URLs)'
Write-Host '------------------------------------------------------'
Write-Host '  SHA256 inventory:' -ForegroundColor Cyan
Get-Content -LiteralPath (Join-Path $stage ('SHA256_' + $Version + '.txt')) -Encoding UTF8
Write-Host '  Release Notes:' -ForegroundColor Cyan
Get-Content -LiteralPath (Join-Path $stage ('RELEASE_NOTES_' + $Version + '.md')) -Encoding UTF8
Write-Host '------------------------------------------------------'
if ($PrepareOnly) {
    Write-Host ('[SAFE] Prepared only. To publish: .\release_FRBLaunch_GitHub.ps1 -Version ' + $Version + ' -PublishOnly')
    exit 0
}
Write-Host 'Please review SHA256, Release Notes and release_plan.json first.' -ForegroundColor Yellow
if (-not [string]::IsNullOrWhiteSpace($GuiApprovedTag)) {
    if (-not $PublishOnly) { throw 'GuiApprovedTag is supported only with -PublishOnly.' }
    $approved = $GuiApprovedTag
} else {
    $approved = Read-Host ('To publish the GitHub Pre-release, type exactly PUBLISH ' + $tag)
}
if ($approved -cne ('PUBLISH ' + $tag)) {
    Write-Host '[SAFE] Publish cancelled. Staged files preserved.' -ForegroundColor Yellow
    exit 0
}
Invoke-ReleaseStep 'publish' @('--approved-tag', $tag)
Write-Host '[DONE] GitHub Pre-release published; no installed product was updated.' -ForegroundColor Green
Write-Host ('[NEXT] TEST only: .\release_FRBLaunch_GitHub.ps1 -Version ' + $Version + ' -ConfigureTestInstall')
