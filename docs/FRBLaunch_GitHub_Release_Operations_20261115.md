# FRB Launch GitHubリリース運用（Draft / 2026-11-15）

## 今回の変更

- 更新バックアップは、次回ビルドのUpdaterから `%LOCALAPPDATA%\FRBLaunch\UpdateBackups\<インストール先名＋識別子>\<日時_ID>` へ作成する。
- 旧保存先の `F:\FRB_Update_Test\.FRBLaunch_update_backups` は**消さない／動かさない**。新Updaterは旧・新両方のJournalを確認・復旧する。
- 保存先はユーザー単位、インストール先単位で分ける。Cドライブの空き容量には注意する（更新前のバックアップ容量を確保する）。
- `%LOCALAPPDATA%` が取得できないWindows環境では更新を停止する（誤った場所へ逃げない）。
- 自動削除・既存バックアップ移行は行わない。復旧の確実性を優先する。

## リリース運用（更新番号の例：統合版0.9.6）

`F:\FRB_Apps\FRB_Launch` に差分を展開してから使う。

**重要：Launch自身の埋め込みバージョン（`src/app_version.py`）は、ビルド後に変更できない。**
Launchのバージョンを上げたい場合は、先に `src/app_version.py` の `APP_VERSION` を変えてから手動ビルドする。
指定しなければ、リリーススクリプトがソースの `APP_VERSION` を採用する。統合版とLaunch版は別番号でよい。

### 1. Launchを手動ビルド

```powershell
cd F:\FRB_Apps\FRB_Launch
.\_build_windows.bat
```

※Studioのソースを変更している場合はStudio側のNativeShellも先にビルドすること。

### 2. 配布物を準備（推奨：一度止めて確認）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\release_FRBLaunch_GitHub.ps1 -Version 0.9.6 -PrepareOnly
```

- Updaterは**スクリプト内で自動ビルド**される（Tcl/Tk混入チェックも従来どおり）。
- Source/EXEのタイムスタンプ、統合バージョン、コンポーネントバージョン、ZIPマニフェスト、SHA-256、Feed URL、簡易認証情報検査を行う。
- ZIPは `F:\FRB_Apps\FRB_Release_Output\github_0.9.6\` に保存する。
- 既存ZIPやGitHub公開アセットは**上書きしない**。
- 個人用メニュー、通常URL、PCローカルパスはユーザー承認済みとして保持する。認証情報だけは検査対象。

### 3. 目視確認後に公開

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\release_FRBLaunch_GitHub.ps1 -Version 0.9.6 -PublishOnly
```

`SHA256_0.9.6.txt`、`release_plan.json`、`RELEASE_NOTES_0.9.6.md` を確認し、プロンプトに次の文字列を**正確に**入力すると公開する。

```text
PUBLISH v0.9.6
```

承認文字列が異なる場合は公開しない。
GitHubに既存Releaseがあれば内容を検査し、不足アセットのみ追加する。ハッシュが異なる既存アセットは拒否する。

**固定URLのPreview Feed:** `-PublishOnly` で公開が完了すると、同じGitHubリポジトリの `main/release-feed/preview/` 内の2つのFeedを順次更新する（Updater→製品）。配布ZIPはバージョン付きの不変URLに置くが、利用者は固定URLを参照し続ける。再公開・失敗時の再実行に対応し、同一バージョンのFeedが別内容なら停止する。

- `https://raw.githubusercontent.com/tamasub/FRB-Launch/main/release-feed/preview/product_feed.json`
- `https://raw.githubusercontent.com/tamasub/FRB-Launch/main/release-feed/preview/updater_feed.json`

Preview Feedの変更はGitHubリポジトリへコミットを作る操作でもある。**ユーザー承認の `PUBLISH vX.Y.Z` はReleaseアセット公開＋Preview Feed更新の両方を許可する。** リリース公開だけ成功してFeed更新に失敗した場合は、`-PublishOnly` を再実行して続きを検証する。

一発で「準備→最終確認→公開」まで行いたい場合は `-PrepareOnly` と `-PublishOnly` の両方を付けずに実行する。確認入力は必須。

### 4. ローカル更新試験環境をGitHubへ接続（任意）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\release_FRBLaunch_GitHub.ps1 -Version 0.9.6 -ConfigureTestInstall
```

既知の `F:\FRB_Update_Test\FRBLaunch` **のみ**Feed設定を変更。現在のインストール済み版が指定の統合版以上なら停止。更新は自動実行しない。

この設定先は上の**固定Preview Feed URL**。これ以降、次版0.9.7を公開してFeedを進めれば、古い0.9.6はURLを変更せず次版を検知できる。**過去の0.9.5固定タグFeedからは一度だけ切替が必要**（設定スクリプトが行う）。

Launchを起動して更新画面から手動実行し、完了後に最新版判定・進捗100%・復旧Journal・Expの登録パスを確認する。

## 中断・障害時の原則

- Journalの `phase=applying` が残る場合、まずUpdaterの `recover` で復旧する。
- `.FRBLaunch_update_backups` と AppData側のバックアップを、動作確認前に削除しない。
- `-PrepareOnly` で途中停止しても、生成物が整合する場合は再実行できる。片方しかZIPがない等、曖昧な状態は**手動確認で停止**する。
- GitHub Releaseの `Source code (zip)` はGitHubにPush済みのコミット内容を示し、リリースへ添付したバイナリの元ソースが自動でPushされるわけではない。ソース公開も目的なら別途commit/pushとタグの対応確認が必要。

## 注意点

Windowsでのリリーススクリプト実行は未確認。GitHub公開も未実行。構文・Python回帰テストまでを提供している。
