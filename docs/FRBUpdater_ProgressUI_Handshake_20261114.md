# FRB Updater — 進捗表示が見えない問題への対策（2026-11-14）

## 実機観測と問題の切り分け

- 更新0.9.0→0.9.1はUpdaterログに `[SUCCESS]` / `[RESTART]` / `[COMPLETED]`、計5,110件の検証が記録されている。
- しかしLaunchから起動した場合、タスクマネージャーでは `FRBUpdater.exe` が動いていても**進捗ウィンドウが見えなかった**。
- 直接 `recover --show-progress` を起動したときは、ネイティブの進捗ウィンドウが表示された。
- 正確な原因はWindows実機のウィンドウ状態・起動ログで再検証が必要。Launch→Updater間に画面表示完了の確認がなく、また従来コードにはGUI起動失敗時の**画面なし更新継続**が存在することはソースから確認できた。
- タスクマネージャー上の「Updater 2個」はPyInstaller `--onefile` の親子プロセスである可能性があり、単独では異常と判定しない。

## 修正

1. **Updaterを前面表示**: Win32 `ShowWindow` / `SetWindowPos(HWND_TOPMOST)`、最善努力で `SetForegroundWindow`。一度目のShowWindowが起動情報に影響される場合も考慮し、二度呼び出す。
2. **操作中表示**: データ総数がまだ分からない待機・取得準備中はMarquee表示。総数ありなら各工程を%表示。進捗メッセージの仕様は既存のイベントを流用する。
3. **起動ハンドシェイク**: Launchが起動ごとに一意の準備完了ファイル (`updater_ui_<uuid>.json`) を渡す。UpdaterがGUIを生成した後に `ready` を通知。Launchは`ready`を読み取るまでは終了しない。その後だけ `.go` ファイルで更新開始を許可し、Launchが終了する。
4. **Fail Closed**: GUI生成に失敗した `apply` は無画面継続しない。Launchは画面が起動できなければ原因を表示し、利用者からの新しい操作を待つ。無許可のUpdaterは45秒で終了し、Systemに触らない。
5. **画面単体テスト**: `FRBUpdater.exe ui-test --show-progress`。更新処理・ダウンロード・Journal・設定変更は一切しない。
6. Journal本体・SHA-256・復旧処理・ユーザー管理データには一切変更なし。`recover` 単独起動時のフォールバックも維持。

## 安全な適用順序（Windows）

1. 差分ZIPを `F:\FRB_Apps\FRB_Launch` の**ソースルート**へパス保持のまま展開。
2. Launch/Studioの実行を終えて、必要に応じて `.venv\Scripts\python.exe -m pytest -q tests/test_updater_progress_handshake_20261114.py tests/test_updater_native_progress_20261114.py` を実行。
3. `_build_updater_windows.bat` で新Updaterをビルド。`[OK] Native Updater archive: no tkinter/Tcl runtime hook` が出ること。
4. 製品更新を伴わない画面テスト: `& 'F:\FRB_Apps\FRB_Launch\dist\updater\FRBUpdater.exe' ui-test --show-progress`。
5. `stage_FRBUpdater_0.9.3_progress_test.ps1` は修正版Updaterのビルドと `FRBUpdater_0.9.3.exe` 配置、ローカルUpdater Feed更新を行う。**製品Feedは変えない・更新は開始しない**。既存0.9.2のEXEは上書きしない。
6. **Launch側ハンドシェイク**を実際に検証するには `_build_windows.bat` でLaunchを再ビルドしたうえ、統合版0.9.2以降など、現在のインストール版（統合0.9.1）より新しいリリースZIPを別途作成する必要がある。既存の0.9.1配布ZIPを上書きしてはならない。製品Feedもその新しいZIPへ更新する。
7. 新しいテスト版で「最新版を確認」→「更新を開始」。期待：Launchに「Updater進捗画面の表示を確認しています...」→Updater前面に工程進捗→Launch終了→更新完了とLaunch再起動。

**注意:** `installed_release.json` を手動で0.9.0に書き換えて同版を再インストールするなどの擬似バージョンダウン操作は行わないこと。現在のテスト環境は統合0.9.1で最新版。既存更新ZIP(0.9.1)を再実行できないのは正常。

## 制約・検証

- Windowsの描画・フォーカス・PyInstaller起動を直接検証できない実行環境のため、Windows実機での見え方は未確認。
- Linuxのpytestで、GUI生成失敗時に更新が開始されないこと、UI準備完了までJournalが変わらないこと、Launchからの許可後に復旧が進むこと、二重実行しないこと、Updaterフィード起動引数、UI単体テストを確認。
- Feed URL設定が更新ZIP内の `defs/update/update_sources.json` で上書きされる問題は**未修正**。次期改修でUserConfig等への分離を検討。現時点では別途ローカルFeed復元が必要。
