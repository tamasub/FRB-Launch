# FRB Launch — 設定JSONにドロップ登録したファイルのアイコン表示修正

更新日: 2026-11-23

## 現象

Files Exp で設定JSON由来のフォルダーを選ぶと、Files List に登録済みの Excel（`.xlsx`）、TXT（`.txt`）、Markdown（`.md`）などが、OS関連付けアイコンではなく汎用ファイルアイコンで表示される。

## 原因

登録処理 `launch_menu_registration.records_for_sources` は、パスを `launch_actions[0].launch_target` に保存する。一方、`launch_virtual_tree.virtual_list_rows` は Files List を仮想ビューとして保つために `_file` を削除する。従来の `file_icon_policy.icon_lookup` は `_file` などしか参照しないので、`icon_key=file` という汎用アイコンへフォールバックしていた。

## 対応

- `src/file_icon_policy.py`: `icon_key=file` の登録済みファイルについて、表示用に `launch_actions[].launch_target` の `Open` ファイルパスを読む。
- 通常ファイルは拡張子を抽出して既存の `Launcher.row_icon` → `QFileIconProvider` に委ねる（例 `.xlsx` は Windows 側で関連付けたファイル種類のアイコン）。
- `.exe` / `.lnk` / `.ico` / `.url` / `.appref-ms` は従来どおりパス別のアイコン参照。
- URL、任意コマンド、ユーザーが別アイコンを指定した項目、フォルダー・ドライブは変更しない。
- 既存設定JSONを再保存・再登録する必要はない。実ファイルを開かずに拡張子だけを使用するため、クラウドのオフラインファイルでも表示判定できる。
- アイコン表示のために仮想ビューへ `_file` を再挿入しない。ファイル操作/実行ルート/設定保存経路は変更しない。

## 修正対象

- `src/file_icon_policy.py`（差し替え）
- `tests/test_registered_json_filetype_icons_20261123.py`（追加）
- `docs/CHANGE_NOTE_RegisteredJsonFileIcons_20261123.md`（追加）

## テスト

```powershell
python -m pytest -q tests/test_cloud_filetype_icons_20261026.py tests/test_registered_json_filetype_icons_20261123.py tests/test_launch_virtual_explorer_split_20261103.py tests/test_launch_0269_page_root_file_drop_20261111.py
```

結果: **24 passed**（Linuxのロジックテスト）。

別途、過去の追加テストに以下の既存前提違いを確認：
- `config/frb_launch_data.json` がZIPに同梱されておらず、当該ファイル必須の一部テストが失敗。
- 2026年10月の一部UIテストは現行ソースの名称・構造と一致せず失敗。

今回の修正に対応するテストはすべて PASS。PySide6 / Windows実機はこの実行環境では利用できないため、Windowsの関連付けアイコン実描画については未確認。

## Windowsでの確認

1. 差分ZIPの `src/file_icon_policy.py` を既存の同名ファイルへ上書き（適用前にバックアップ）。
2. FRB Launchを再起動（Python版で確認。exe版を使う場合は再ビルドが必要）。
3. 設定JSONに登録済みの `Book1.xlsx`、`001_1.txt`、`frblaunch_memo.md` 等をFiles Listで開き、Windowsでの関連付けアイコンを確認する。
4. URL・フォルダー・独自指定アイコンが従来どおりであることを確認する。

Windows側で拡張子の関連付けを変更すると、表示アイコンもWindowsの状態に依存する。
