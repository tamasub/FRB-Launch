# FRB Launch 0.9.5 GitHub pre-release staging / explicit publishing / HTTPS test
# Windows PowerShell 5.1 compatible. NO UPDATE IS STARTED BY THIS SCRIPT.
param(
    [string]$Repo = 'tamasub/FRB-Launch',
    [string]$LaunchSource = 'F:\FRB_Apps\FRB_Launch',
    [string]$StudioSource = 'F:\FRB_Apps\FRB_Studio',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$PublishRelease,
    [switch]$ConfigureTestInstall
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($PublishRelease -and $ConfigureTestInstall) { throw 'Run publishing and test configuration as separate steps.' }
if ($Repo -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$') { throw 'Repo must be owner/repo' }
$LaunchSource = [IO.Path]::GetFullPath($LaunchSource)
$StudioSource = [IO.Path]::GetFullPath($StudioSource)
$ReleaseDir = [IO.Path]::GetFullPath($ReleaseDir)
$TestInstallRoot = [IO.Path]::GetFullPath($TestInstallRoot)
$stage = Join-Path $ReleaseDir 'github_0.9.5'
$python = Join-Path $LaunchSource '.venv\Scripts\python.exe'
$builder = Join-Path $LaunchSource 'scripts\build_portable_distribution.py'
$helper = Join-Path $LaunchSource 'scripts\prepare_github_release_095.py'
$tag = 'v0.9.5'
$productZip = Join-Path $stage 'FRBLaunch_0.9.5_update.zip'
$portableZip = Join-Path $stage 'FRBLaunch_0.9.5_portable.zip'
$updaterExe = Join-Path $stage 'FRBUpdater_0.9.5.exe'
$feeds = @((Join-Path $stage 'product_feed.json'), (Join-Path $stage 'updater_feed.json'))
foreach ($file in @($python, $builder, $helper)) { if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing: $file" } }

if (-not $PublishRelease -and -not $ConfigureTestInstall) {
    Write-Host '[1/2] Stage GitHub pre-release files (no upload)...' -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $productZip) -and -not (Test-Path -LiteralPath $portableZip)) {
        $appVersion = Get-Content -LiteralPath (Join-Path $LaunchSource 'src\app_version.py') -Raw -Encoding UTF8
        if ($appVersion -notmatch "(?m)^APP_VERSION\s*=\s*'0\.9\.3'\s*$") { throw 'Launch APP_VERSION must be 0.9.3.' }
        $launchExe = Join-Path $LaunchSource 'dist\FRBLaunch\FRBLaunch.exe'
        $updaterBuild = Join-Path $LaunchSource 'dist\updater\FRBUpdater.exe'
        foreach ($file in @($launchExe, $updaterBuild)) { if (-not (Test-Path -LiteralPath $file)) { throw "Rebuild missing EXE: $file" } }
        $launchSourceVersion = Join-Path $LaunchSource 'src\app_version.py'
        $updaterSourceUi = Join-Path $LaunchSource 'src\frb_update\progress_ui.py'
        if ((Get-Item -LiteralPath $launchExe).LastWriteTimeUtc -lt (Get-Item -LiteralPath $launchSourceVersion).LastWriteTimeUtc) {
            throw "Launch EXE older than source. Rebuild: $launchSourceVersion"
        }
        if ((Get-Item -LiteralPath $updaterBuild).LastWriteTimeUtc -lt (Get-Item -LiteralPath $updaterSourceUi).LastWriteTimeUtc) {
            throw "Updater EXE older than source. Rebuild: $updaterSourceUi"
        }
        New-Item -ItemType Directory -Path $stage -Force | Out-Null
        # DO NOT pass --archive-url here. Existing System config is deliberately blank;
        # generating a GitHub feed from staged immutable artifacts avoids changing it.
        & $python $builder --launch-source $LaunchSource --studio-source $StudioSource --output $stage `
            --version 0.9.5 --launch-version 0.9.3 --studio-version 0.9.0 --updater-version 0.9.5 `
            --notes 'GitHub Pre-release update test: UI polish / quiet notices / ZIP source roots' `
            --approve-template
        if ($LASTEXITCODE -ne 0) { throw 'Integrated 0.9.5 bundle build failed.' }
    } elseif (-not (Test-Path -LiteralPath $productZip) -or -not (Test-Path -LiteralPath $portableZip)) {
        throw 'Partial output ZIPs found. No overwrite: inspect stage and finish safely.'
    } else {
        Write-Host '[INFO] Reuse existing 0.9.5 ZIPs without overwriting.'
    }
    Write-Host '[2/2] Validate staged release and generate fixed-tag HTTPS feed JSON...' -ForegroundColor Cyan
    & $python $helper --phase stage --repo $Repo --stage $stage --source $LaunchSource
    if ($LASTEXITCODE -ne 0) { throw 'Stage validation/feed creation failed.' }
    Write-Host '[SAFE] Prepared. Nothing uploaded or installed.' -ForegroundColor Green
    Write-Host "[NEXT] Publish by rerunning with -PublishRelease -Repo $Repo"
    exit 0
}

Write-Host '[VERIFY] Check immutable artifacts and HTTPS feed schema...' -ForegroundColor Cyan
& $python $helper --phase verify --repo $Repo --stage $stage --source $LaunchSource
if ($LASTEXITCODE -ne 0) { throw 'Release preflight failed. First run without switches to prepare.' }

if ($PublishRelease) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) is missing. Install it and run gh auth login.' }
    & gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI not authenticated. Run: gh auth login' }
    $infoText = (& gh repo view $Repo --json nameWithOwner,isPrivate 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw "Repository not accessible: $Repo. Create it in GitHub first. $infoText" }
    $info = $infoText | ConvertFrom-Json
    if ($info.isPrivate) { throw 'Private repo Release assets require authentication. Use a public repository for ordinary Updater HTTPS downloads.' }
    $assets = @($productZip, $portableZip, $updaterExe, (Join-Path $stage 'SHA256_0.9.5.txt'), `
        (Join-Path $stage 'product_feed.json'), (Join-Path $stage 'updater_feed.json'))
    # Windows PowerShell 5.1: gh writes "release not found" to stderr for a missing tag.
    # With ErrorActionPreference=Stop, even stderr redirected to $null can abort
    # the entire script before LASTEXITCODE is inspected. Capture stderr using
    # Start-Process so a missing release is handled as the normal first-publish case.
    $ghExe = (Get-Command gh -ErrorAction Stop).Source
    $probeOut = Join-Path $env:TEMP ("frb_gh_release_stdout_" + [Guid]::NewGuid().ToString('N') + '.txt')
    $probeErr = Join-Path $env:TEMP ("frb_gh_release_stderr_" + [Guid]::NewGuid().ToString('N') + '.txt')
    try {
        $probe = Start-Process -FilePath $ghExe -ArgumentList @(
            'release', 'view', $tag, '--repo', $Repo, '--json', 'assets,isPrerelease'
        ) -NoNewWindow -Wait -PassThru -RedirectStandardOutput $probeOut -RedirectStandardError $probeErr
        $probeExitCode = $probe.ExitCode
        $existingText = [IO.File]::ReadAllText($probeOut, [Text.Encoding]::UTF8).Trim()
        $probeError = [IO.File]::ReadAllText($probeErr, [Text.Encoding]::UTF8).Trim()
    } finally {
        Remove-Item -LiteralPath $probeOut, $probeErr -Force -ErrorAction SilentlyContinue
    }
    if ($probeExitCode -ne 0 -and (($probeError + "`n" + $existingText) -notmatch '(?i)(release not found|HTTP 404|404 Not Found)')) {
        throw "GitHub release lookup failed (exit $probeExitCode): $probeError $existingText"
    }
    if ($probeExitCode -ne 0) {
        Write-Host "[PUBLISH] Release $tag does not exist yet; creating pre-release..." -ForegroundColor Yellow
        & gh release create $tag @assets --repo $Repo --title 'FRB Launch 0.9.5 — Preview' `
            --prerelease --notes-file (Join-Path $stage 'RELEASE_NOTES_0.9.5.md')
        if ($LASTEXITCODE -ne 0) { throw 'GitHub Release creation failed.' }
    } else {
        $existing = $existingText | ConvertFrom-Json
        if (-not $existing.isPrerelease) { throw 'Existing tag is NOT a prerelease. Refusing to modify.' }
        $uploaded = @{}
        foreach ($entry in $existing.assets) { $uploaded[$entry.name] = $entry }
        $missing = @()
        foreach ($file in $assets) {
            $name = Split-Path $file -Leaf
            if (-not $uploaded.ContainsKey($name)) { $missing += $file }
            elseif ($uploaded[$name].size -ne $null -and [long]$uploaded[$name].size -ne (Get-Item -LiteralPath $file).Length) {
                throw "Existing GitHub asset $name has a different size. Refusing overwrite."
            }
        }
        if ($missing.Count -gt 0) {
            Write-Host '[PUBLISH] Upload only missing assets to existing Pre-release...' -ForegroundColor Yellow
            & gh release upload $tag @missing --repo $Repo
            if ($LASTEXITCODE -ne 0) { throw 'GitHub Release missing-asset upload failed.' }
        } else { Write-Host '[OK] All release assets already exist; not uploading again.' }
    }
    & $python $helper --phase online --repo $Repo --stage $stage
    if ($LASTEXITCODE -ne 0) { throw 'Published feed/asset HTTPS verification failed. Do not start update.' }
    Write-Host "[OK] Release: https://github.com/$Repo/releases/tag/$tag" -ForegroundColor Green
    Write-Host '[NEXT] Rerun with -ConfigureTestInstall to switch ONLY the test install Feed URLs.'
    exit 0
}

if ($ConfigureTestInstall) {
    # Validate the remote release anonymously; NEVER write config before verification.
    & $python $helper --phase configure --repo $Repo --stage $stage --test-install $TestInstallRoot
    if ($LASTEXITCODE -ne 0) { throw 'Test HTTPS Feed config failed.' }
    Write-Host '[SAFE] No update executed. Launch test install and use Version Info -> Update manually.' -ForegroundColor Green
}
