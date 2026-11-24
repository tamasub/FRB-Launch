# FRB Commander 初号機（First Challenge） — 2026-11-23

## 基準

- 適用基準：`launch_app_20261123_170144.zip`
- 形態：**差分ZIP**。Launch配下で動くPython / PySide6 6.10.1モジュール。
- 今回はWindows実機のGUI動作確認は未実施（この環境にはPySide6 / Windowsがない）。
- `.viewdef` はJSON形式のUTF-8ファイル。従来のStudio ViewDefの移行は**対象外**。

## 適用

1. FRB Launchのフォルダーをバックアップし、差分ZIPをLaunchフォルダーへ**フォルダー構造を維持して上書き展開**。
2. `examples/commander/Export-DiffToJson.viewdef` をコピーし、**既存**の `Export-DiffToJson.ps1` が置かれているフォルダーへ、隣同士になるよう配置。
3. Launchを再起動する。
4. Launch内のFiles Listで `Export-DiffToJson.ps1` を選択し、右クリック／`Shift+F10`／メニューキーで、`FRB Commanderで実行` を選ぶ。
5. `↓` で「比較方法」を開き「2ファイル比較」を選択。`↑↓` で候補を動かし、`→` / `Enter` で確定。
6. 比較元ファイル選択用Keyboard Exが起動する。既存の検索・`←→` を使用。ファイル上の `→` / `Enter` は**ファイルを開かず**選択結果を返す。
7. 比較先ファイル選択用Keyboard Exは、**比較元ファイルの親フォルダー**から起動する。
8. Commander上で `←→` はパンくずのフォーカス移動、`↓` はそのくずの選び直し。`Ctrl+Enter` で実行確認、**明示的に「はい」を選択した場合のみ**実行。
9. 出力ログと終了コードはCommanderのウィンドウ内に表示される。

## ViewDefの最初の契約

- 起動対象：右クリックされた `.ps1` に限定。`.viewdef` 内の `script.file` は同じフォルダーの実際のスクリプト名と一致させる。
- `schema_version`: `frb_commander_viewdef_v0.1`
- `view_type`: `frb_commander`
- `steps`: 選択項目・`visible_when`・選択候補・`selector` を宣言。
- 対応セレクター: `keyboard_ex.file`
- `initial_location.type`: `workspace_root` / `parent_of` / `script_dir`
- `workspace_root`: 選択スクリプトを含むLaunchの登録済みFilesルートのうち最も広いルート。該当しなければスクリプト配置フォルダー。
- `parent_of`: `selection` で指定した先行ファイルの親フォルダー。
- PowerShellには引数配列で値を渡す（文字列をシェル結合しない）。
- 一度作ったViewDefと、Keyboard Exの選択体験を次のスクリプトでも再利用できる設計を目指す。

## 対象外・初号機の制約

- `MaxPatchChars`、`Unified`、`NoPatch`、`OutputPath` 等の詳細設定は**未実装**（元スクリプトのデフォルトが使われる）。
- `.bat` / `.py` と独立EXE起動、ViewDefの自動作成、Studio既存ViewDefの移行は対象外。
- 実行するPowerShellにはGitなど**元スクリプト自身が要求する環境・依存ファイル**が必要。ViewDefは実行依存を解消しない。
- パンくず上の選択結果は再編集できる。コマンドライン文字列の表示・直接編集はしない。
- Launch内でのモーダル/非モーダルのWindowsフォーカス挙動、Keyboard Exのファイル返却、PowerShellの実行結果は**実機で受入確認が必要**。
- 出力先の `DiffToJson_current.json` は、元スクリプトにより上書きされる可能性がある。テストはコピーしたJSONデータとバックアップ可能な環境で行うこと。

## 実装ファイル

- `src/commander/viewdef.py`: 定義の検証／選択経路／引数生成
- `src/commander/window.py`: キーボード操作・選択状態・実行確認・QProcess
- `src/commander/launch_adapter.py`: Launch Files登録ルートから作業起点を解決
- `src/slash_exp_navigation.py`: Keyboard Exの「実行せずパスだけ返す」モード
- `src/app.py`: 右クリックメニューで起動（既存メニューが閉じた後）
- `config/context_menu_options.json`、`src/context_menu_config.py`、`src/context_menu_icons.py`: 宣言型メニュー項目の追加
- `examples/commander/Export-DiffToJson.viewdef`: 2ファイル比較用ViewDefサンプル
- `tests/test_commander_viewdef_v01.py`: 定義の解釈／引数配列／Keyboard Exの選択専用動作
- `tests/test_context_menu_filesystem.py`: 追加メニューを反映した期待値更新

## テスト結果（コンテナのヘッドレス試験）

`PYTHONPATH=src pytest -q tests/test_commander_viewdef_v01.py tests/test_context_menu_filesystem.py tests/test_context_menu_json_separator_paste_20261025.py tests/test_files_column_context_common_20261112.py tests/test_slash_exp_navigation_20261118.py tests/test_slash_exp_keyboard_ex_breadcrumb_20261120.py tests/test_slash_exp_three_menu_polish_20261120.py`

**109 passed, 11 subtests passed**。Qt実体を用いたWindowsGUI実機テストではない。

補足：別の既存テスト `tests/test_slash_exp_extended_ui_20261118.py` の `test_obsidian_handoff_does_not_modify_vault_theme_and_monitor_only_hwnd` は今回変更していない `src/studio_preview_panel.py` 内の期待文字列が一致せず失敗することを確認。今回の差分とは別件。
