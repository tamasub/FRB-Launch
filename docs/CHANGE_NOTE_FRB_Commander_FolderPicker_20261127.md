# FRB Commander — Keyboard Ex フォルダー選択

対象: launch_app_20261127_181739.zip。差分を既存Launchルートに上書き展開する。

- ViewDef v0.1 に `folder_path` / `keyboard_ex.folder` を互換追加。既存 file_path / text / single_choice は維持。
- Keyboard Exをフォルダー専用選択モードで開く。ファイル非表示。Enter=選択、→=子列、←=戻る、Esc=取消。各列先頭の「（このフォルダーを選択）」は現在のディレクトリを確定。マウスではフォルダー行で子列、先頭行で確定。空フォルダーも可。
- 選択結果はパスのみ。Files Listの移動・ファイル実行・コンテキスト操作は行わない。コマンド生成時にディレクトリの実在を確認。
- 初期位置は既存のworkspace_root/script_dir/parent_of（先行file_pathの親）の契約を流用。workspace_root はPS1を含む最も広い登録済みルート、なければPS1の親。初期位置より外への移動は未対応。
- `cmd_count_source_steps.viewdef` のrootをfolder_pathへ変更。PS1本体は変更なし。BAT追加なし。
- 作成用JSON Schema・ガイドも更新。新しいViewDefは更新前のCommanderでは動かない。

## 検証

- 新規5テストPASS：Schema（既存2例も検証）、通常/Git差分argv、日本語・空白・&入りパス、ファイル/存在しないフォルダーの拒否、子列/空フォルダー/現在位置/取消、Launch側ナビゲーションを呼ばないこと。
- `pytest -q tests/test_commander*py tests/test_slash_exp*py tests/test_keyboard_ex*py`：146 PASS、4 SKIP、8 FAIL。元ZIPで同じ既存8件FAIL（旧テーマ/配置/Obsidian関連）、141 PASS、4 SKIP。今回追加の失敗なし。
- Python構文検査PASS。Windows/PySide6実機UIおよびPS1実行は未検証。
