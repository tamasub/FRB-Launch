# FRB Launch GitHub リリースGUI — v0.1

## 目的

「昨日の日付と同じく、毎回リリース番号を入力したくない」を解決する。`_build_windows.bat` はこれまでどおり手動。**Windows PowerShell 5.1とWinForms**だけで動作し、PyInstaller / tkinter は使用しない。

## 差分の配置

このZIPを `F:\FRB_Apps\FRB_Launch` に上書き展開する。

- `release_FRBLaunch_GUI.ps1` — GUI本体（UTF-8 BOM、Windows PowerShell 5.1対応ソース）
- `FRB_Release_Manager.vbs` — ダブルクリックでGUI起動（コンソール非表示）
- `FRB_Release_Manager_debug.bat` — GUIが出ない場合、エラーメッセージを見るための起動用
- `release_FRBLaunch_GitHub.ps1` — 既存CLIに `-GuiApprovedTag` を追加した差分。通常の `Read-Host` は維持
- `tests/test_release_gui_20261115.py` — 設計上の安全ガードに関する静的テスト

## 使い方

1. 今までどおり、まず `_build_windows.bat` でLaunchを手動ビルドする。
2. `FRB_Release_Manager.vbs` をダブルクリック。
3. GitHubの既存Releaseを自動取得。たとえば最新版 `v0.9.6` なら、初期表示で **次版 `0.9.7`** を提案。`パッチ／マイナー／メジャー` も選べる（通常はパッチ）。
4. **① 準備・検証（公開なし）** を押す。従来の `-PrepareOnly` と同じ処理を行う（必要ならUpdaterをビルド、ZIP・Feed・SHA・planを生成・照合）。
5. 表示されたSHA-256とログを確認する。
6. **② GitHubに公開** を押すと、タグ・リリースノート・SHA-256の確認ダイアログが出る。**「はい」** を選んだ時だけ既存の `-PublishOnly` と同じ処理を実行する。公開成功時は固定Preview Feedも進む。
7. 配布された製品は**自動更新しない**。Launch側の更新操作はユーザーが実行する。

**統合版のバージョン**はGitHubから自動提案する。**Launch本体のバージョン**は `src/app_version.py` に固定され、GUIから勝手に変えない。Launch本体の番号も上げたい場合は手動ビルドする**前**に変更する。

## 安全性と注意

- このGUIは `release_FRBLaunch_GitHub.ps1` を呼ぶ操作画面。既存の `release_plan.json`、SHA-256検証、既存の同名アセットの上書き禁止、認証検査、Preview Feed更新の安全対策は変更しない。
- 最初のボタンは**GitHubに公開しない**。GitHubへの公開は必ず別ボタンと最終確認ダイアログを経る。
- GitHubからリリース番号を取得できないときは、自動採番を行わず操作を停止する。勝手に `0.0.1` から始めない。
- 公開途中で失敗した場合、**GitHub Releaseは部分的に作成されている可能性がある**。同じ版で再度準備・検証し、安全な再試行ができることを確認してから公開する。
- GUIログは `%LOCALAPPDATA%\FRBLaunch\ReleaseLogs` に保存。
- ローカルPCのパスは既存作業環境（`F:\FRB_Apps`）を前提とする。現在のGitHubリポジトリは `tamasub/FRB-Launch`。
- CLIを使う場合は従来どおり `-PrepareOnly` と `-PublishOnly`＋`PUBLISH vX.Y.Z` が使える。
- Windows実機でのWinForms起動、GitHub操作は**未確認**。最初は必ず「①準備・検証」までで操作と表示を確認し、公開は確認してから。

## 補足

「DOSの入力プロンプト」の初期入力は環境依存の補助機能で実現する方法もあるが、PowerShell 5.1・別プロセス・リリース承認の組み合わせには向いていない。このGUIは **入力を不要にして、承認だけ人間に残す** 方針。
