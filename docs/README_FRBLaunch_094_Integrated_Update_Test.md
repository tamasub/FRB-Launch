# FRB Launch 0.9.4 ローカル更新テスト（PRIVATE_REVIEW）

対象: **統合版 0.9.3 → 0.9.4** / Launch **0.9.1 → 0.9.2** / Studio **0.9.0 維持** / Updater **0.9.3 → 0.9.4**。

## 準備

- この差分ZIPを `F:\FRB_Apps\FRB_Launch` に上書き展開。
- 必ず **LaunchとStudioを全終了**（トレイ常駐も終了）。ビルド対象の開発ソースを更新済みであること。
- `F:\FRB_Apps\FRB_Studio\NativeShell\_publish\FRBStudio.NativeShell.exe` が存在すること。
- `F:\FRB_Update_Test\FRBLaunch` に統合版0.9.3がインストールされていること。
- 更新Journalに `phase=applying` があれば**先に旧版へ復旧**。`*.bak`や更新バックアップは削除しない。
- これはローカル試験のみ。既存の0.9.3 ZIP、過去Updater実行ファイルは上書きしない。

### 1. Launchを再ビルド

変更済み `src/app_version.py` は既に `0.9.2`。**Studio詳細設定／Exp登録先の実機確認済みのソース**をビルドする。

```powershell
cd F:\FRB_Apps\FRB_Launch
.\_build_windows.bat
```

ビルド済みLaunch.exeが変更ソースより古い場合は次の準備スクリプトが停止する。

### 2. 0.9.4 Updaterビルド・配布ZIP・Feed作成

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBLaunch_0.9.4_update_test.ps1
```

行うこと: 更新テスト用インストール版と未完了Journal確認 → Updater 0.9.4をTkinterなしでビルド → 既存Launch 0.9.2ビルドを検証 → 統合版0.9.4更新ZIP/portable ZIPを新規作成（5,000件超の完全マニフェスト検証あり） → `FRBUpdater_0.9.4.exe` を配布 → SHA-256付きUpdater Feed・Product Feedを書き換え（元Feedを`.bak`に保存） → テストインストール先の **SystemとUserConfigの両方** にローカルFeed URLを書き込む（既存差分を`.bak`保存）。更新本体は**起動しない**。

前回のように途中でFeed生成に失敗しても、ビルド済ZIPを**再生成せず**続行できる。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBLaunch_0.9.4_update_test.ps1 -ResumeAfterBuild
```

### 3. テスト環境から一回だけ更新

`F:\FRB_Update_Test\FRBLaunch\FRBLaunch.exe` を起動 → **最新版を確認** → 統合版0.9.4 / Updater0.9.4 / Launch0.9.2を確認 → **更新を開始**。

進捗ウィンドウが出ること、検証／展開／適用の値が動くこと、最終バーが**100%**になること、成功後Launchが自動起動することを確認。途中でLaunchやStudioを追加起動しない。

### 4. 更新後の最重要確認（Feedを手直しする前に！）

再起動したLaunchで「最新版を確認」→ **最新版を使用しています。** と出ること。ここでURL未設定が再発しないかが**今回の修正検証**。先に手作業でFeedを再設定してしまうと、欠陥の再発を見逃す。

次に、ExpのLaunch/Studioの登録先が `F:\FRB_Apps` を指しているか、メニューITEM詳細設定からStudioが開くかを確認する。

**注意:** 以前のテスト環境が個人の `%LOCALAPPDATA%\FRBLaunch\UserData` を共有している場合、Exp登録JSONはユーザーデータ側に存在する。Updaterはこのデータを変更しない。テスト環境で開発用パスに解決されることを確認する。

### 5. 失敗時

- 既に作った0.9.4 ZIPを変えない。`-ResumeAfterBuild` でFeed生成のみ再実行。
- 更新成功後、どうしてもFeedを復元する必要が出たときだけ以下を実行。**テスト評価のスクショ／ログ採取後**に行う。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBLaunch_0.9.4_update_test.ps1 -RefreshConfigOnly
```

- `phase=applying` のJournalが残っている場合は**更新を押さず**、復旧処理を行う。
- `F:\FRB_Update_Test\.FRBLaunch_update_backups` は削除しない。
- 成功確認用のログ: `%LOCALAPPDATA%\FRBLaunch\UpdateLogs\updater_*.log`（PowerShell 5.1なら `Get-Content -Encoding UTF8`）。

## 制約

- PRIVATE_REVIEW ONLY。デフォルト初期設定・個人パス等は外部公開前に承認が必要。
- 0.9.4新規アーカイブの再書込・既存0.9.3アーカイブの変更は行わない。
- **テスト環境以外のインストール先には書き込まない。**
- UserDataやJournalには書き込まない。UserConfigのFeed設定だけはテストのため明示的に更新する。
- Windows実機でのビルド・GUI更新は利用者側での確認が必要。
