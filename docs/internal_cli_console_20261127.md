# 内部CLIのコンソール非表示化（2026-11-27）

基準: launch_app_20261127_202822.zip

## Context / Expected
ExplorerからLaunchへのファイル・フォルダーDropによる登録時、内部CLIのコンソールを人間に表示しない。登録処理の結果・エラー処理・検証/コミット順序は従来どおり。明示的にコンソールを表示するRunやターミナル起動には影響させない。

## 原因候補と対応
`handle_launch_drop` → `_registration_commit` → `commit_add` → Node Studio Change Core (dry_run / commit)。従来は `subprocess.run` に Windows の CREATE_NO_WINDOW が指定されていなかった。実機再現は未確認だが、両方の起動でコンソール生成を抑止する。

`process_runner.py` に `_console_options` と `run_internal_process` を設け、既存 `start_process` と Windows のコンソール方針を共有する。内部CLIの標準入出力、UTF-8、タイムアウト、終了コードを維持する。`launch_menu_registration.py` の2つの起動箇所を共通関数へ接続する。登録だけでなく同一Change Coreを利用する登録解除、簡易編集、移動、Page操作も対象。他の独立したCLI起動経路（Option Composer、Git等）は今回変更しない。

## 検証
- 新規テスト8件 PASS（Windows起動フラグはモック、非Windowsの実プロセス入出力も確認）。
- 関連テスト合計45 PASS / 1 FAIL / 11 SKIP（新規8件を含む、別途2 subtests PASS）。
- FAIL: `test_gui_three_fields_no_path_ui_and_remote_assisted_dialogs`。元ZIPに戻して同じFAILを確認済み。
- 添付ZIPに config/frb_launch_data.json がないため、関連既存テストでは同梱 defaults/frb_launch_data.template.json を一時配置し、終了後削除した。差分には含めない。
- Studio実体を必要とする統合テストはSKIP。Windows/PySide6実機の画面検証は未実施。

## 実機確認
Explorerから登録先へファイル/フォルダーをDropし、登録が成功しDOS画面が出ないこと。明示的なターミナル/コンソール起動は従来どおり表示されること。
