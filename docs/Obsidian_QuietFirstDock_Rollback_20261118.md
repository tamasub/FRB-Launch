# FRB Launch — Obsidian初回の静音入室対策を取り消す（差分）

## 戻す範囲
直前の `FRBLaunch_Obsidian_QuietFirstDock_20261118_diff.zip` による変更**だけ**を取り消す。
`launch_app_20261118_193842.zip` から以下の２ファイルを完全復元する。
- `src/external_win32_host.py`
- `src/studio_preview_panel.py`

Obsidianの左サイドバー自動クローズ・２つ目のMarkdownを既存ポップアウトで開く改善は維持。Studioやサクラのコードは変更しない。

## 適用方法
FRB Launch終了後、このZIPをFRB Launchルートへ展開し、同名の２ファイルを上書き。Launchを再起動する。Studioの再ビルドは不要。

直前の追加ファイル `src/obsidian_quiet_window.py` は参照されなくなるため、残しても実行には影響しない。完全に整理したい場合に限り削除してよい。`tests/test_obsidian_quiet_window_20261118.py`、`docs/Obsidian_QuietFirstDock_20261118.md` も今回の試作専用で、削除は任意。

Windows実機での動作検証は未実施。
