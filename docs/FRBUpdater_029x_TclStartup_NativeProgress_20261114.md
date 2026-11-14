# FRB Updater — Tcl起動失敗と中断Journalの復旧

日付: 2026-11-14 / 修正範囲: FRB Updater の進捗UI、PyInstallerビルド検査、復旧補助BAT

## 現象と原因

- Windowsで新しくビルドした `FRBUpdater.exe` を起動すると、PyInstaller の `pyi_rth__tkinter` が `_MEI.../_tcl_data` 未検出で例外終了した。
- 復旧用 `recover` も Updater 本体が起動できないため走らず、前回の `journal.json` に `phase=applying` が残りうる。
- 今回の直接原因は、Updaterの進捗UI `frb_update/progress_ui.py` の `tkinter` 依存と、そのTcl/TkデータをPyInstaller単一EXEに正常に含められなかった構成。Windows PythonのTcl/Tk同梱状態などの影響を受ける。
- 復旧処理 `frb_update/updater_core.py` はこのエラーより後で実行されるため、今回は変更していない。**アップデータが処理に入る前に落ちていた**ことが問題。

## 対応内容

1. `progress_ui.py` を Windows 標準 `user32` + `comctl32` (ctypes) の進捗ウィンドウへ移行。Qt/Tk/Tcl のランタイム不要。バックグラウンドの処理は1回だけ起動し、画面更新はメインスレッドで実行。更新中は閉じられない。
2. `_build_updater_windows.bat` は明示的に `tkinter` / `_tkinter` を除外してPyInstallerを起動。
3. `scripts/verify_updater_binary.py` でビルド後のEXEアーカイブ（同梱PYZを含む）からTk関連コード・起動フックの混入を検出した場合、配布を停止。
4. `_recover_updater_windows.bat` は**明示指定された配置先**のみを `recover`。成功してもLaunchは勝手に再起動しない。
5. 既存のJournal・バックアップ・更新コア・ユーザーデータへの変更なし。

## 最優先：中断Journalの復旧（Windows PC）

**Launch/Studioをすべて終了したまま**、必ず `phase=applying` の前回中断を復旧してから次の更新テストへ。

1. 差分ZIPを `FRB_Launch` ソースのルートへ、相対パスを維持して上書き展開する。
2. ソースルートで `_build_updater_windows.bat` を実行する。最後に `[OK] Native Updater archive: no tkinter/Tcl runtime hook` が出ること。
3. 次のコマンドの配置先は例（エラー画像で指定されていたテストフォルダー）。**実際に復旧したい配置先かどうか必ず確認**して実行。

```powershell
& 'F:\FRB_Apps\FRB_Launch\dist\updater\FRBUpdater.exe' recover `
  --install-root 'F:\FRB_Update_Test\FRBLaunch' `
  --show-progress
```

代わりに、ソースルートのコマンドプロンプトで：

```bat
_recover_updater_windows.bat "F:\FRB_Update_Test\FRBLaunch"
```

4. `旧版への復旧が完了` を確認。更新結果は `%LOCALAPPDATA%\FRBLaunch\UpdateLogs\last_update_status.json`、詳細ログは同フォルダーの `updater_*.log`。
5. `.FRBLaunch_update_backups` を削除しない。Journalが `rolled_back` になることを確認する。※ほかにも中断Journalがある場合はすべて復旧される。
6. 再度更新テストをするなら、**今作り直したUpdater.exe** で新しいUpdater Feed（旧版と異なるversion + 実EXEのSHA-256 + size）を生成し、テスト用Feedに反映。旧版のEXE/Feedが再利用されないようにする。製品版ZIPの再作成も必要に応じて行う。

## 検証

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_updater_native_progress_20261114.py `
  tests/test_updater_recovery_lock_20261114.py `
  tests/test_updater_lifecycle_v0_2_20261114.py `
  tests/test_frb_updater_family_20261114.py
```

Linux環境では対象回帰テストをパスしたが、**WindowsネイティブUIの描画とPyInstallerでのEXE作成・起動についてはWindows実機確認が必要**。Windows上で `recover` を実行した時点で、初めて実際のインストールフォルダーが復旧される。

### 注意

- 更新・復旧の作業中はLaunch/Studioを起動しない。
- 古いUpdater.exeはそのまま。今回のソース差分だけを展開しても、既存EXEは自動修復されない。**新ビルドが必須。**
- 今回の差分ZIPにWindows実行ファイル、ユーザーデータ、Journal、配布Feed、個人設定は含まれない。
