# FRB Launch 0.9.5 向け差分：バージョン情報・ZIP登録先・Updater UI

対象：`F:\FRB_Apps\FRB_Launch` の **0.9.4修正適用済みソース**。

## 変更内容

- 設定メニューは「バージョン情報...」へ統一。旧「バージョン情報」の別ポップアップはメニューから外す。
- バージョン情報を開くと、最新版を非同期で**自動確認**。ボタンは「再確認」用に維持。
- ライトモードのバージョン表示を濃い緑の文字色に変更（可読性向上）。
- 起動後、Feedが正しく設定されている製品版だけ、バックグラウンドで更新の有無を**静かに確認**。新しい統合版を見つけたときだけ設定アイコンの右に小さな情報アイコン。クリックでバージョン情報を開く。通信失敗はポップアップなし。**自動更新は一切しない**。
- Updater進捗の「展開（準備）」と「インストール先への反映」を明確化。フォントを `Yu Gothic UI` に統一し、各コントロールの右端を揃える。Tcl/Tk依存は増やさない。
- ZIP作成メニューのLaunchソース・Studioソースのルートを固定。既存UserDataは登録済みIDの旧値だけ修復し、変更前データを `UserData\_Backups` に保存。
- 次回用Launchバージョンを `0.9.3` に更新。統合版`0.9.5`／Updater`0.9.5`の配布テストを想定。

## 1. ソースへ適用

1. LaunchとStudioを終了（Updater処理・Journalが進行中なら触らない）。
2. 差分ZIPを `F:\FRB_Apps\FRB_Launch` へ上書き展開。
3. 先に既存UserDataに変更が必要か確認する。

```powershell
cd F:\FRB_Apps\FRB_Launch
powershell -NoProfile -ExecutionPolicy Bypass -File .\repair_FRBLaunch_zip_paths.ps1 -DryRun
```

内容を確認したらLaunchとStudioを閉じた状態で実際に修復する。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\repair_FRBLaunch_zip_paths.ps1
```

対象フォルダーが存在しない場合は修正を中止する。ユーザーが明示的に指定した**別のカスタムパスは上書きしない**。

## 2. 開発版動作確認

```powershell
.\_build_windows.bat
.\_build_updater_windows.bat
```

- Launchバージョン情報：現在版が`Launch 0.9.3`、開くと自動確認されること。
- ライトモード文字が読めること。
- ソース版ExpとZIP作成を実際に動作確認すること。
- 更新のない状態では新バージョンアイコンなし。新しい統合版を検知したときだけ設定の隣に情報マーク。
- Updaterの単独表示テスト（更新しない）：

```powershell
& 'F:\FRB_Apps\FRB_Launch\dist\updater\FRBUpdater.exe' ui-test --show-progress
```

## 3. GitHub更新テストへの移行（まだ公開しない）

1. まず統合版0.9.5／Launch 0.9.3／Studio 0.9.0／Updater 0.9.5 で**ローカルの実更新**を確認する。
2. `FRB_Release_Output` の PRIVATE_REVIEW ZIP・`defaults`の個人用パス、トークン、OneDriveパス、テストFeed `file://` を**公開しない**。配布対象を精査し、必要なら専用のクリーンな公開テンプレートを作成する。
3. GitHubへはまずPre-releaseで配布物を登録し、公式HTTPSダウンロード先を使ったFeed（schema/version/size/sha256）が実際の公開アセットと一致するか検証する。
4. `allow_local_for_test`は本番ではfalse。URLはHTTPSのみ。ローカルFeedをGitHub公開Feedに切り替えたあと、テスト環境のLaunchから**手動更新**。新バージョン通知、進捗、完了、Feed保持、再確認、Studio・ZIP起動を確認する。
5. 中断Journalやバックアップが残っている場合は更新テストを中止。過去のリリースアセットは書き換えず新バージョンとしてリリースする。

## テスト

- Python: 新規静的・Dataテストを含む関連テストを実施。
- 注意：Linux上ではWindowsネイティブウィンドウを起動できないため、フォントの実描画、Win32進捗バー、PyInstaller EXE動作は**未検証**。Windowsで目視確認する。
- `config/frb_launch_data.json`（個人用設定）は差分ZIPに含めない。バックアップやJournalも含めない。
