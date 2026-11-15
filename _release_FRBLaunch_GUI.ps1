# FRB Launch GitHub Release Manager
# Windows PowerShell 5.1 / WinForms / UTF-8 BOM / STA.
# No auto publish: two explicit user actions, prepare then publish.
# _build_windows.bat remains manual; do not touch app_version.py.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$script:Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:Pipeline = Join-Path $script:Root 'release_FRBLaunch_GitHub.ps1'
$script:Repo = 'tamasub/FRB-Launch'
$script:ReleaseDir = 'F:\FRB_Apps\FRB_Release_Output'
$script:LatestRemote = ''
$script:SelectedVersion = ''
$script:PreparedVersion = ''
$script:PreparedNotes = ''
$script:Published = $false
$script:Job = $null
$script:LastDisplayed = ''
$script:PreviewURL = 'https://github.com/tamasub/FRB-Launch/releases'
$script:RemoteReady = $false
$script:ReleaseNotes = 'FRB Launch usability and updater improvements'

if (-not (Test-Path -LiteralPath $script:Pipeline -PathType Leaf)) {
    [System.Windows.Forms.MessageBox]::Show('release_FRBLaunch_GitHub.ps1 が見つかりません。', 'FRB Release') | Out-Null
    exit 1
}

function SemverTuple([string]$version) {
    if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)$') { throw ('Invalid version: ' + $version) }
    return @([int]$Matches[1], [int]$Matches[2], [int]$Matches[3])
}
function NextVersion([string]$current, [string]$kind) {
    $v = @(SemverTuple $current)
    switch ($kind) {
        'Minor' { return ('{0}.{1}.0' -f $v[0],($v[1]+1)) }
        'Major' { return ('{0}.0.0' -f ($v[0]+1)) }
        default { return ('{0}.{1}.{2}' -f $v[0],$v[1],($v[2]+1)) }
    }
}
function VersionCode([string]$version) {
    $v = @(SemverTuple $version)
    return ([long]$v[0] * 1000000000000L + [long]$v[1] * 1000000L + [long]$v[2])
}
# Windows PowerShell 5.1 can preserve a JSON array as a nested Object[].
# Normalize every element before inspecting its properties (0 / 1 / N releases).
function Expand-ReleaseRows([object]$item) {
    if ($null -eq $item) { return }
    if ($item -is [System.Array]) {
        foreach ($child in $item) { Expand-ReleaseRows $child }
        return
    }
    Write-Output -NoEnumerate $item
}
function Get-ReleaseVersions([string]$rawJson) {
    $json = $rawJson.Trim()
    if (-not $json.StartsWith('[')) { throw 'GitHub Release一覧のJSON形式が不正です。' }
    $parsed = ConvertFrom-Json -InputObject $json -ErrorAction Stop
    $versions = @()
    foreach ($r in @(Expand-ReleaseRows $parsed)) {
        if ($null -eq $r) { continue }
        $draftProp = $r.PSObject.Properties['isDraft']
        $tagProp = $r.PSObject.Properties['tagName']
        if ($null -eq $draftProp -or $null -eq $tagProp) {
            throw 'GitHub Release一覧の項目が不足しています。'
        }
        if ([bool]$draftProp.Value) { continue }
        $tag = [string]$tagProp.Value
        if ($tag -match '^v(\d+\.\d+\.\d+)$') { $versions += $Matches[1] }
    }
    return $versions
}
function SharedText([string]$path) {
    if (-not [System.IO.File]::Exists($path)) { return '' }
    $stream = [System.IO.File]::Open($path,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
    try {
        $reader = [System.IO.StreamReader]::new($stream,[System.Text.Encoding]::UTF8,$true)
        try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally { $stream.Dispose() }
}
function AddLine([string]$line) {
    if ($script:log.TextLength -gt 50000) { $script:log.Text = $script:log.Text.Substring($script:log.TextLength-40000) }
    $script:log.AppendText($line + [Environment]::NewLine)
    $script:log.SelectionStart = $script:log.TextLength
    $script:log.ScrollToCaret()
}
function Status([string]$message) { $script:status.Text = $message }
function Get-LaunchVersion {
    $file = Join-Path $script:Root 'src\app_version.py'
    if (-not (Test-Path -LiteralPath $file)) { return '(not found)' }
    $data = [System.IO.File]::ReadAllText($file,[System.Text.Encoding]::UTF8)
    $match = [regex]::Match($data, 'APP_VERSION\s*=\s*[''\"](?<v>\d+\.\d+\.\d+)[''\"]')
    if ($match.Success) { return $match.Groups['v'].Value }
    return '(unknown)'
}
function Update-SelectedVersion {
    if (-not $script:RemoteReady) { return }
    $kind = 'Patch'
    if ($script:kind.SelectedIndex -eq 1) { $kind='Minor' }
    if ($script:kind.SelectedIndex -eq 2) { $kind='Major' }
    $script:SelectedVersion = NextVersion $script:LatestRemote $kind
    $script:next.Text = '次の統合版  ' + $script:SelectedVersion
    $script:prepare.Enabled = $true
    # The prepared artifacts are only valid for the exact version and notes.
    $script:publish.Enabled = ($script:PreparedVersion -eq $script:SelectedVersion -and
        $script:PreparedNotes -ceq $script:notes.Text.Trim() -and -not $script:Published)
}
function RefreshButtons([bool]$busy) {
    $script:discover.Enabled = -not $busy
    $script:kind.Enabled = -not $busy
    $script:notes.Enabled = -not $busy
    $script:prepare.Enabled = (-not $busy -and $script:RemoteReady)
    $script:publish.Enabled = (-not $busy -and $script:RemoteReady -and
        $script:PreparedVersion -eq $script:SelectedVersion -and
        $script:PreparedNotes -ceq $script:notes.Text.Trim() -and -not $script:Published)
    $script:bar.Visible = $busy
    if ($busy) { $script:bar.Style = 'Marquee' } else { $script:bar.Style='Continuous'; $script:bar.Value=0 }
}
function BeginJob([string]$type) {
    if ($null -ne $script:Job) { return }
    try {
        $dir = Join-Path $env:LOCALAPPDATA 'FRBLaunch\ReleaseLogs'
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
        $stem = 'release_ui_' + [DateTime]::Now.ToString('yyyyMMdd_HHmmss_fff') + '_' + [Guid]::NewGuid().ToString('N').Substring(0,6)
        $stdout = Join-Path $dir ($stem + '.out.log')
        $stderr = Join-Path $dir ($stem + '.err.log')
        if ($type -eq 'DISCOVER') {
            $gh = (Get-Command gh.exe -ErrorAction Stop).Source
            $command = 'release list --repo ' + $script:Repo + ' --limit 100 --json tagName,isDraft'
            $exe = $gh
            $targetVer = ''
        } elseif ($type -eq 'DISCOVER_FEED') {
            # GitHub Releases can be empty after deletion. The fixed Preview Feed
            # retains the last published version and is used ONLY for numbering.
            $gh = (Get-Command gh.exe -ErrorAction Stop).Source
            $command = 'api repos/' + $script:Repo + '/contents/release-feed/preview/product_feed.json?ref=main'
            $exe = $gh
            $targetVer = ''
        } else {
            $exe = Join-Path $PSHOME 'powershell.exe'
            $targetVer = $script:SelectedVersion
            $command = '-NoProfile -ExecutionPolicy Bypass -File "' + $script:Pipeline + '" -Version ' + $targetVer
            if ($type -eq 'PREPARE') {
                $script:PreparedVersion=''
                $script:PreparedNotes=''
                $command += ' -PrepareOnly'
            } elseif ($type -eq 'PUBLISH') {
                # Approval is generated ONLY following the Publish button and confirmation dialog.
                $command += ' -PublishOnly -GuiApprovedTag "PUBLISH v' + $targetVer + '"'
            }
            if ($script:notes.Text.Trim() -ne '') {
                # Explicitly exclude command-line quoting/control metacharacters.
                $safeNotes = $script:notes.Text.Trim()
                if ($safeNotes -match '["\r\n]') { throw 'リリースノートにはダブルクォート・改行を使えません。' }
                $command += ' -Notes "' + $safeNotes + '"'
            }
        }
        $process = Start-Process -FilePath $exe -ArgumentList $command -WorkingDirectory $script:Root `
            -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
        $script:Job = @{ Process=$process; Type=$type; Version=$targetVer; Output=$stdout; Error=$stderr }
        $script:LastDisplayed=''
        RefreshButtons $true
        Status('実行中：' + $type + '  ' + $targetVer)
        AddLine('> ' + $type + '  ' + $targetVer)
        $script:timer.Start()
    } catch {
        Status('開始失敗：' + $_.Exception.Message)
        AddLine('[ERROR] ' + $_.Exception.Message)
        RefreshButtons $false
    }
}
function FinishJob([hashtable]$job, [int]$exitCode, [string]$stdout, [string]$stderr) {
    $type=$job.Type
    $script:Job=$null
    RefreshButtons $false
    if ($exitCode -ne 0) {
        AddLine('[ERROR] ' + $type + ' failed (exit ' + $exitCode + '). Logs: ' + $job.Output)
        if ($type -eq 'DISCOVER_FEED') {
            Status('Release 0件。Preview Feedも取得できないため、次版を自動決定できません。')
            AddLine('[SAFE] 公開済Releaseと固定Preview Feedの両方がありません。勝手な採番は行いません。')
        } else {
            Status('失敗：' + $type + '。下のログを確認してください。')
        }
        return
    }
    if ($type -eq 'DISCOVER') {
        try {
            # Normalize JSON arrays before evaluating release properties.
            # In PowerShell 5.1, a one-item JSON array may remain nested.
            $versions = @(Get-ReleaseVersions $stdout)
            if ($versions.Count -eq 0) {
                $script:latest.Text = 'GitHub Release  0件'
                $script:RemoteReady = $false
                Status('公開済Releaseなし。固定Preview Feedから採番基準を確認します…')
                AddLine('[INFO] 公開済Release 0件。固定Preview Feedを確認します。')
                BeginJob 'DISCOVER_FEED'
                return
            }
            $script:LatestRemote = ($versions | Sort-Object { VersionCode $_ } -Descending | Select-Object -First 1)
            $script:latest.Text = 'GitHub最新版  v' + $script:LatestRemote
            $script:RemoteReady = $true
            $script:Published = $false
            Update-SelectedVersion
            Status('最新版を取得しました。ビルド済みなら「準備・検証」へ。')
            AddLine('[OK] GitHub latest v' + $script:LatestRemote + ' / source Launch ' + (Get-LaunchVersion))
        } catch {
            $script:RemoteReady=$false
            Status('バージョン取得失敗：' + $_.Exception.Message)
            AddLine('[ERROR] ' + $_.Exception.Message)
        }
    } elseif ($type -eq 'DISCOVER_FEED') {
        try {
            $response = ConvertFrom-Json -InputObject $stdout -ErrorAction Stop
            if ($null -eq $response) { throw 'Preview Feed取得結果が空です。' }
            $contentProp = $response.PSObject.Properties['content']
            if ($null -eq $contentProp -or [string]::IsNullOrWhiteSpace([string]$contentProp.Value)) {
                throw 'GitHub Contents APIにcontentがありません。'
            }
            $bytes = [Convert]::FromBase64String(([string]$contentProp.Value -replace '\s', ''))
            $json = [System.Text.Encoding]::UTF8.GetString($bytes).TrimStart([char]0xFEFF)
            $feed = ConvertFrom-Json -InputObject $json -ErrorAction Stop
            if ($null -eq $feed -or $feed.schema -cne 'frb-product-feed-v1' -or
                $feed.product -cne 'FRBLaunchIntegrated') {
                throw 'Preview Feedのschema/productが一致しません。'
            }
            $baseline = [string]$feed.version
            if ($baseline -notmatch '^\d+\.\d+\.\d+$') {
                throw 'Preview Feedのversionが正しくありません。'
            }
            $script:LatestRemote = $baseline
            $script:latest.Text = 'GitHub Release  0件'
            $script:RemoteReady = $true
            $script:Published = $false
            Update-SelectedVersion
            Status('Release 0件。Preview Feed v' + $baseline + ' を基準に次版を提案しました。')
            AddLine('[OK] Release 0件 / Preview Feed v' + $baseline + ' -> candidate v' + $script:SelectedVersion)
            AddLine('[INFO] Preview Feedは過去の配布情報です。削除済みReleaseが現存するという意味ではありません。')
        } catch {
            $script:RemoteReady = $false
            Status('Release 0件。Preview Feedを解釈できず、採番を中止しました。')
            AddLine('[ERROR] Preview Feed: ' + $_.Exception.Message)
        }
    } elseif ($type -eq 'PREPARE') {
        $stage = Join-Path $script:ReleaseDir ('github_' + $job.Version)
        $planFile = Join-Path $stage 'release_plan.json'
        $shaFile = Join-Path $stage ('SHA256_' + $job.Version + '.txt')
        if ((Test-Path -LiteralPath $planFile) -and (Test-Path -LiteralPath $shaFile)) {
            $plan = Get-Content -LiteralPath $planFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($plan.tag -ne ('v' + $job.Version)) { Status('検証失敗：リリース計画とバージョンが不一致'); return }
            $script:PreparedVersion = $job.Version
            $script:PreparedNotes = $script:notes.Text.Trim()
            AddLine('----- SHA-256 (公開前確認用) -----')
            AddLine((Get-Content -LiteralPath $shaFile -Raw -Encoding UTF8).TrimEnd())
            AddLine('----- release_plan.json: ' + $planFile)
            Status('準備・検証OK：v' + $job.Version + '。内容を確認して公開できます。')
            RefreshButtons $false
        } else {
            Status('検証結果ファイルがありません。公開はできません。')
        }
    } elseif ($type -eq 'PUBLISH') {
        $script:Published = $true
        Status('GitHub公開完了：v' + $job.Version + '（インストール済み製品は未変更）')
        AddLine('[OK] https://github.com/' + $script:Repo + '/releases/tag/v' + $job.Version)
        RefreshButtons $false
        [System.Windows.Forms.MessageBox]::Show(
           'GitHubに v' + $job.Version + ' を公開しました。' + [Environment]::NewLine +
           '次回もGitHubの最新版から自動採番できます。',
           'FRB Launch Release', 'OK', 'Information') | Out-Null
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'FRB Launch  |  GitHub リリース管理'
$form.Width=810; $form.Height=715
$form.StartPosition='CenterScreen'; $form.MinimumSize=[System.Drawing.Size]::new(700,620)
$form.BackColor=[System.Drawing.Color]::FromArgb(245,248,247)
$form.Font=[System.Drawing.Font]::new('Yu Gothic UI',10)
$form.AutoScaleMode = 'Dpi'

function LabelAt($text,$x,$y,$w,$h,$size=10,$bold=$false) {
    $l=New-Object System.Windows.Forms.Label
    $l.Text=$text; $l.Location=[System.Drawing.Point]::new($x,$y); $l.Size=[System.Drawing.Size]::new($w,$h)
    if ($bold) {$style=[System.Drawing.FontStyle]::Bold} else {$style=[System.Drawing.FontStyle]::Regular}
    $l.Font=[System.Drawing.Font]::new('Yu Gothic UI',$size,$style)
    $l.AutoEllipsis=$true; $form.Controls.Add($l)
    return $l
}
function ButtonAt($text,$x,$y,$w,$h) {
    $b=New-Object System.Windows.Forms.Button
    $b.Text=$text; $b.Location=[System.Drawing.Point]::new($x,$y)
    $b.Size=[System.Drawing.Size]::new($w,$h)
    $b.FlatStyle='System'; $form.Controls.Add($b)
    return $b
}
$null=LabelAt 'FRB Launch  |  GitHub リリース' 24 15 610 38 17 $true
$null=LabelAt '手動ビルドの後は、次の版を選ぶ → 検証 → 公開だけ。更新は勝手に開始しません。' 26 54 740 24 9
$script:latest=LabelAt 'GitHub最新版  読み込み中…' 28 99 280 32 11 $true
$script:next=LabelAt '次の統合版  —' 328 99 280 32 12 $true
$script:discover=ButtonAt '最新版を再取得' 633 98 145 33
$null=LabelAt '更新区分' 29 150 95 30 10
$script:kind=New-Object System.Windows.Forms.ComboBox
$script:kind.Location=[System.Drawing.Point]::new(121,148)
$script:kind.Size=[System.Drawing.Size]::new(170,30)
$script:kind.DropDownStyle='DropDownList'
[void]$script:kind.Items.AddRange(@('パッチ  +0.0.1','マイナー  +0.1.0','メジャー  +1.0.0'))
$script:kind.SelectedIndex=0
$form.Controls.Add($script:kind)
$script:sourceVersion=LabelAt ('Launch本体のソース版: ' + (Get-LaunchVersion) + '  ※番号変更には手動ビルドが必要') 311 151 470 28 9
$null=LabelAt '変更内容（Release Notes）' 28 201 260 27 10
$script:notes=New-Object System.Windows.Forms.TextBox
$script:notes.Location=[System.Drawing.Point]::new(27,231)
$script:notes.Size=[System.Drawing.Size]::new(750,27)
$script:notes.Text=$script:ReleaseNotes
$script:notes.Anchor='Top,Left,Right'
$form.Controls.Add($script:notes)
$script:prepare=ButtonAt '① 準備・検証（公開なし）' 27 282 285 43
$script:publish=ButtonAt '② GitHubに公開' 329 282 224 43
$script:publish.Enabled=$false
$script:openGitHub=ButtonAt 'GitHubを開く' 572 282 205 43
$script:status=LabelAt 'GitHubの最新リリースを確認しています…' 28 340 750 31 10 $true
$script:bar=New-Object System.Windows.Forms.ProgressBar
$script:bar.Location=[System.Drawing.Point]::new(28,373)
$script:bar.Size=[System.Drawing.Size]::new(748,9)
$script:bar.Anchor='Top,Left,Right'
$script:bar.Visible=$false; $form.Controls.Add($script:bar)
$null=LabelAt '実行ログ ／ SHA-256 ／ エラー詳細' 28 396 600 24 10 $true
$script:log=New-Object System.Windows.Forms.TextBox
$script:log.Multiline=$true; $script:log.ReadOnly=$true
$script:log.ScrollBars='Both';$script:log.WordWrap=$false
$script:log.Font=[System.Drawing.Font]::new('Consolas',9)
$script:log.BackColor=[System.Drawing.Color]::White
$script:log.Location=[System.Drawing.Point]::new(27,427)
$script:log.Size=[System.Drawing.Size]::new(750,215)
$script:log.Anchor='Top,Bottom,Left,Right'
$form.Controls.Add($script:log)
$footer=LabelAt '公開は明示的なクリック＋最終確認が必要です。既存Releaseは無断上書きしません。' 29 650 745 26 9
$footer.Anchor='Bottom,Left,Right'
$script:log.Anchor='Top,Bottom,Left,Right'

$script:kind.Add_SelectedIndexChanged({
    $script:PreparedVersion=''; $script:PreparedNotes=''; Update-SelectedVersion
})
$script:notes.Add_TextChanged({
    if ($null -eq $script:Job) { RefreshButtons $false }
})
$script:discover.Add_Click({
    $script:RemoteReady=$false
    $script:PreparedVersion='';$script:PreparedNotes=''
    RefreshButtons $true
    BeginJob 'DISCOVER'
})
$script:prepare.Add_Click({
    if ($script:SelectedVersion -notmatch '^\d+\.\d+\.\d+$') { return }
    if ([string]::IsNullOrWhiteSpace($script:notes.Text)) { Status('変更内容を入力してください。'); return }
    if ($script:notes.Text -match '["\r\n]') { Status('変更内容にダブルクォートと改行は使えません。'); return }
    BeginJob 'PREPARE'
})
$script:publish.Add_Click({
    if ($script:PreparedVersion -cne $script:SelectedVersion -or
        $script:PreparedNotes -cne $script:notes.Text.Trim() -or $script:Published) {
        Status('準備・検証が必要です。');return
    }
    $stage = Join-Path $script:ReleaseDir ('github_' + $script:SelectedVersion)
    $shaFile = Join-Path $stage ('SHA256_' + $script:SelectedVersion + '.txt')
    if (-not (Test-Path -LiteralPath $shaFile)) { Status('SHA-256がありません。公開できません。');return }
    $inventory=(Get-Content -LiteralPath $shaFile -Raw -Encoding UTF8).TrimEnd()
    $message = ('次の内容をGitHub Public Pre-releaseへ公開します。' + [Environment]::NewLine +
        'Repo: '+ $script:Repo + [Environment]::NewLine + 'Tag: v' + $script:SelectedVersion +
        [Environment]::NewLine + 'Changes: ' + $script:notes.Text.Trim() +
        [Environment]::NewLine + [Environment]::NewLine + 'SHA256:' + [Environment]::NewLine +
        $inventory + [Environment]::NewLine + [Environment]::NewLine +
        '本当に公開しますか？（公開後、Preview Feedも切り替えます）')
    $answer=[System.Windows.Forms.MessageBox]::Show($message,'公開の最終承認',
        [System.Windows.Forms.MessageBoxButtons]::YesNo,[System.Windows.Forms.MessageBoxIcon]::Warning,
        [System.Windows.Forms.MessageBoxDefaultButton]::Button2)
    if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) { BeginJob 'PUBLISH' }
})
$script:openGitHub.Add_Click({ Start-Process $script:PreviewURL })

$script:timer=New-Object System.Windows.Forms.Timer
$script:timer.Interval=500
$script:timer.Add_Tick({
    if ($null -eq $script:Job) { $script:timer.Stop(); return }
    $job=$script:Job
    $out = SharedText $job.Output
    $err = SharedText $job.Error
    $combined = $out
    if (-not [string]::IsNullOrWhiteSpace($err)) { $combined += [Environment]::NewLine + '[STDERR]' + [Environment]::NewLine + $err }
    if ($combined -ne $script:LastDisplayed) {
        # Only append the new suffix, preserve existing stage log and scrolling.
        if ($combined.StartsWith($script:LastDisplayed)) {
            $suffix=$combined.Substring($script:LastDisplayed.Length)
            if ($suffix.Length -gt 0) { $script:log.AppendText($suffix) }
        } else {
            $script:log.AppendText([Environment]::NewLine + $combined)
        }
        $script:LastDisplayed=$combined
        $script:log.SelectionStart=$script:log.TextLength
        $script:log.ScrollToCaret()
    }
    $job.Process.Refresh()
    if ($job.Process.HasExited) {
        $script:timer.Stop()
        # Final read after exit ensures complete JSON and log content.
        $out = SharedText $job.Output
        $err = SharedText $job.Error
        $code = $job.Process.ExitCode
        try {
            FinishJob $job $code $out $err
        } catch {
            $script:Job = $null
            $script:PreparedVersion = ''
            $script:PreparedNotes = ''
            RefreshButtons $false
            Status('処理結果の解釈でエラー: ' + $_.Exception.Message)
            AddLine('[ERROR] Result parsing: ' + $_.Exception.Message)
        }
        $job.Process.Dispose()
    }
})
$form.Add_FormClosing({
    param($sender,$e)
    if ($null -ne $script:Job) {
        $e.Cancel=$true
        Status('処理中です。完了してから閉じてください。')
    }
})
$form.Add_Shown({
    BeginJob 'DISCOVER'
})
RefreshButtons $true
[void][System.Windows.Forms.Application]::Run($form)
