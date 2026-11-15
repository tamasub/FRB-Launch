# FRB Updater 0.9.6: handshake race hotfix. Windows PowerShell 5.1.
# Three explicit, separate phases: stage (default), publish, configure TEST install.
# The integrated 0.9.5 GitHub release and its immutable ZIPs are NEVER changed.
param(
    [string]$Repo = 'tamasub/FRB-Launch',
    [string]$LaunchSource = 'F:\FRB_Apps\FRB_Launch',
    [string]$ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output',
    [string]$TestInstallRoot = 'F:\FRB_Update_Test\FRBLaunch',
    [switch]$PublishHotfix,
    [switch]$ConfigureTestInstall
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($PublishHotfix -and $ConfigureTestInstall) { throw 'Choose only one phase.' }
if ($Repo -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$') {
    throw 'Repository must be owner/repo.'
}
$LaunchSource = [IO.Path]::GetFullPath($LaunchSource)
$ReleaseDir = [IO.Path]::GetFullPath($ReleaseDir)
$TestInstallRoot = [IO.Path]::GetFullPath($TestInstallRoot)
$stage = Join-Path $ReleaseDir 'github_updater_0.9.6_hotfix'
$tag = 'updater-v0.9.6-hotfix'
$updaterName = 'FRBUpdater_0.9.6.exe'
$updaterFile = Join-Path $stage $updaterName
$feedFile = Join-Path $stage 'updater_feed.json'
$notesFile = Join-Path $stage 'RELEASE_NOTES_Updater_0.9.6.md'
$feedURL = "https://github.com/$Repo/releases/download/$tag/updater_feed.json"
$exeURL = "https://github.com/$Repo/releases/download/$tag/$updaterName"
$productFeedURL = "https://github.com/$Repo/releases/download/v0.9.5/product_feed.json"

function Read-Json([string]$path) {
    return ([IO.File]::ReadAllText($path,[Text.Encoding]::UTF8) | ConvertFrom-Json)
}
function Write-Utf8New([string]$path,[string]$content) {
    if (Test-Path -LiteralPath $path) {
        if ([IO.File]::ReadAllText($path,[Text.Encoding]::UTF8) -ne $content) {
            throw "Existing file differs; refusing overwrite: $path"
        }
        return
    }
    [IO.File]::WriteAllText($path,$content,(New-Object Text.UTF8Encoding($false)))
}
function Verify-Stage {
    if (-not (Test-Path -LiteralPath $updaterFile -PathType Leaf)) { throw "Missing staged EXE: $updaterFile" }
    if (-not (Test-Path -LiteralPath $feedFile -PathType Leaf)) { throw "Missing staged feed: $feedFile" }
    $feed = Read-Json $feedFile
    $size = (Get-Item -LiteralPath $updaterFile).Length
    $sha = (Get-FileHash -LiteralPath $updaterFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($feed.schema -ne 'frb-updater-feed-v1' -or $feed.version -ne '0.9.6' -or
        $feed.url -ne $exeURL -or [long]$feed.size -ne $size -or $feed.sha256 -ne $sha) {
        throw 'Staged Updater feed does not match actual EXE/version/URL.'
    }
    Write-Host "[OK] Updater 0.9.6: size=$size SHA256=$sha" -ForegroundColor Green
}

if (-not $PublishHotfix -and -not $ConfigureTestInstall) {
    $sourceFile = Join-Path $LaunchSource 'src\frb_update\progress_gate.py'
    if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) { throw "Missing source: $sourceFile" }
    $sourceText = [IO.File]::ReadAllText($sourceFile,[Text.Encoding]::UTF8)
    if (-not $sourceText.Contains('PARTIAL_MARKER_GRACE_SECONDS') -or -not $sourceText.Contains('os.replace(temp, go)')) {
        throw 'The progress_gate.py hotfix is not applied. Extract the diff ZIP first.'
    }
    $builder = Join-Path $LaunchSource '_build_updater_windows.bat'
    if (-not (Test-Path -LiteralPath $builder -PathType Leaf)) { throw "Missing Updater builder: $builder" }
    Write-Host '[1/2] Build fixed Updater (no Launch/Studio rebuild)...' -ForegroundColor Cyan
    & cmd.exe /c "`"$builder`""
    if ($LASTEXITCODE -ne 0) { throw 'Updater build failed.' }
    $binary = Join-Path $LaunchSource 'dist\updater\FRBUpdater.exe'
    if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) { throw "Updater EXE missing: $binary" }
    if ((Get-Item $binary).LastWriteTimeUtc -lt (Get-Item $sourceFile).LastWriteTimeUtc) {
        throw 'Updater EXE is older than the hotfix source; refusing to stage.'
    }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Write-Host '[2/2] Stage Updater-only 0.9.6; leave integrated 0.9.5 untouched...' -ForegroundColor Cyan
    $hash = (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant()
    if (Test-Path -LiteralPath $updaterFile) {
        $oldHash = (Get-FileHash -LiteralPath $updaterFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $oldHash) { throw "Staged EXE already exists with DIFFERENT bytes: $updaterFile" }
        Write-Host '[INFO] Existing staged EXE matches current build; reusing.'
    } else {
        Copy-Item -LiteralPath $binary -Destination $updaterFile
    }
    $feedObj = [ordered]@{
        schema = 'frb-updater-feed-v1'
        version = '0.9.6'
        url = $exeURL
        size = [long](Get-Item $updaterFile).Length
        sha256 = $hash
    }
    $feedText = ($feedObj | ConvertTo-Json -Depth 5) + "`n"
    Write-Utf8New $feedFile $feedText
    # External UTF-8 release notes avoid here-string parsing/encoding ambiguity
    # in Windows PowerShell 5.1. Read bytes explicitly as UTF-8.
    $notesTemplate = Join-Path $LaunchSource 'docs\RELEASE_NOTES_Updater_0.9.6.md'
    if (-not (Test-Path -LiteralPath $notesTemplate -PathType Leaf)) {
        throw "Updater release notes template missing: $notesTemplate"
    }
    $notes = [IO.File]::ReadAllText($notesTemplate, [Text.Encoding]::UTF8)
    Write-Utf8New $notesFile ($notes.TrimEnd() + "`n")
    Verify-Stage
    Write-Host '[SAFE] Built and staged locally; nothing uploaded or installed.' -ForegroundColor Green
    Write-Host "[NEXT] Publish: .\prepare_FRBUpdater_0.9.6_GitHub_hotfix.ps1 -PublishHotfix"
    exit 0
}

Verify-Stage
if ($PublishHotfix) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) is missing.' }
    & gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'gh auth login is needed.' }
    $repoJson = (& gh repo view $Repo --json nameWithOwner,isPrivate) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'GitHub repository not accessible.' }
    $r = $repoJson | ConvertFrom-Json
    if ($r.isPrivate) { throw 'Repo is Private. HTTPS Updater requires Public.' }
    # Listing is safe when the tag does not exist; avoids PS5.1 native stderr errors.
    $releaseList = (& gh release list --repo $Repo --limit 100 --json tagName,isPrerelease,isDraft) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'GitHub release list failed.' }
    $found = @($releaseList | ConvertFrom-Json | Where-Object { $_.tagName -eq $tag })
    if ($found.Count -eq 0) {
        Write-Host "[PUBLISH] Creating Updater-only Pre-release: $tag" -ForegroundColor Yellow
        & gh release create $tag $updaterFile $feedFile --repo $Repo --title 'FRB Updater 0.9.6 - Handshake Hotfix' --prerelease --notes-file $notesFile
        if ($LASTEXITCODE -ne 0) { throw 'GitHub release creation failed.' }
    } else {
        Write-Host '[INFO] Release tag already exists; checking without overwriting.'
    }
    $releaseText = (& gh release view $tag --repo $Repo --json isPrerelease,assets) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'Unable to verify the release.' }
    $release = $releaseText | ConvertFrom-Json
    if (-not $release.isPrerelease) { throw 'Expected Pre-release, got a normal release.' }
    foreach ($file in @($updaterFile,$feedFile)) {
        $item = Get-Item -LiteralPath $file
        $asset = @($release.assets | Where-Object { $_.name -eq $item.Name })
        if ($asset.Count -ne 1 -or [long]$asset[0].size -ne $item.Length) {
            throw "Missing or unexpected GitHub asset: $($item.Name)"
        }
    }
    Write-Host "[OK] Published: https://github.com/$Repo/releases/tag/$tag" -ForegroundColor Green
    Write-Host '[NEXT] Configure ONLY test install using -ConfigureTestInstall.'
    exit 0
}

if ($ConfigureTestInstall) {
    # Require public GitHub feed to be reachable BEFORE touching UserConfig.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $remote = Invoke-RestMethod -Uri $feedURL -TimeoutSec 35 -Headers @{'User-Agent'='FRB-Update-Preflight/0.9.6'}
    $local = Read-Json $feedFile
    if ($remote.schema -ne $local.schema -or $remote.version -ne $local.version -or
        $remote.url -ne $local.url -or [long]$remote.size -ne [long]$local.size -or
        $remote.sha256 -ne $local.sha256) { throw 'Published Updater feed differs from local artifact.' }
    $head = Invoke-WebRequest -UseBasicParsing -Method Head -Uri $exeURL -TimeoutSec 35
    if ([int]$head.StatusCode -ne 200) { throw 'GitHub Updater EXE not reachable.' }
    $install = $TestInstallRoot
    if ([IO.Path]::GetFileName($install) -ine 'FRBLaunch' -or
        [IO.Path]::GetFileName([IO.Path]::GetDirectoryName($install)) -ine 'FRB_Update_Test') {
        throw 'Safety guard: only F:\FRB_Update_Test\FRBLaunch-like installation is permitted.'
    }
    $statePath = Join-Path $install 'installed_release.json'
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { throw 'Installed test manifest missing.' }
    $state = Read-Json $statePath
    if ($state.version -ne '0.9.4') { throw "Expected installed integrated version 0.9.4, found $($state.version)." }
    $journalRoot = Join-Path ([IO.Path]::GetDirectoryName($install)) '.FRBLaunch_update_backups'
    if (Test-Path -LiteralPath $journalRoot) {
        Get-ChildItem -LiteralPath $journalRoot -Filter 'journal.json' -Recurse -File | ForEach-Object {
            if ((Read-Json $_.FullName).phase -eq 'applying') { throw "Pending recovery Journal: $($_.FullName)" }
        }
    }
    $userConfig = Join-Path $install 'UserConfig\update_sources.json'
    if (-not (Test-Path -LiteralPath $userConfig -PathType Leaf)) { throw 'Test UserConfig missing; do not invent defaults.' }
    $attr = [IO.File]::GetAttributes($userConfig)
    if (($attr -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Symlinked UserConfig refused.' }
    $config = Read-Json $userConfig
    if ($config.schema -ne 'frb-update-sources-v1' -or $config.product_feed_url -ne $productFeedURL -or
        $config.allow_local_for_test -ne $false) { throw 'Existing product feed differs from v0.9.5 GitHub HTTPS; refusing config rewrite.' }
    if ($config.updater_feed_url -eq $feedURL) {
        Write-Host '[OK] Test UserConfig already points to Updater 0.9.6 and product 0.9.5.' -ForegroundColor Green
        exit 0
    }
    $config.updater_feed_url = $feedURL
    $text = ($config | ConvertTo-Json -Depth 10) + "`n"
    $tmp = $userConfig + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    $bak = $userConfig + '.before_updater096_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.bak'
    try {
        [IO.File]::WriteAllText($tmp,$text,(New-Object Text.UTF8Encoding($false)))
        [IO.File]::Replace($tmp,$userConfig,$bak)
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
    }
    Write-Host "[BACKUP] $bak"
    Write-Host '[OK] Test UserConfig: Updater 0.9.6 / Product 0.9.5' -ForegroundColor Green
    Write-Host '[SAFE] No update started. Launch test install and manually choose Update.'
}
