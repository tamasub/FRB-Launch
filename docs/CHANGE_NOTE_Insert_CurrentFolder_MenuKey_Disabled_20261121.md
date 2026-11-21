# FRB Launch — Insertでカレントフォルダーにワープ / Windows MenuKey無効化

更新日：2026-11-21  
元資材：`launch_app_20261121_170022.zip`  
位置づけ：既存の操作体系を維持した局所改修（データJSON・ViewDefの変更なし）

## 変更内容

### 1. `Insert` でカレントフォルダー操作状態へ

- 対象：Filesワークスペースの**Files List**にキーボードフォーカスがあるとき。
- `Insert` 単独押下で、既存の「とんとん親帰り／カレントフォルダー操作エリア」を**左シングルクリックしたときと同じ処理**を実行する。
- 選択中の子ファイル／フォルダー行をすべて解除。過去の `currentItem` は記憶用の枠線として保持するが、選択対象ではない。
- カレントフォルダーのパス、Files Expの選択、JSON、ファイル実体を変更しない。
- 非同期の自動選択修復が旧ファイルを再選択しないよう `deliberate_blank_selection` をセットする。
- `→` は、旧ファイルでなく**カレントフォルダーの既存背景操作メニュー**へ接続する。
- `↑ / ↓` で通常のList行選択へ復帰する。選択解除中の `Enter` と `F2` は過去のファイルを誤操作しない。
- List以外の入力欄・Browser・編集中のリネームフィールドではInsertを乗っ取らない。

### 2. Windows `MenuKey`（アプリケーションキー）を当面無効化

- Launch本体、Remote、Launch所有のメニュー／ポップアップに対する `Key_Menu` KeyPress/KeyRelease を消費する。
- Windows/Qtが `QContextMenuEvent(Reason.Keyboard)` として配送する場合も消費する。
- `MenuKey` から `→` への変換は廃止。勝手に行を変更しない、サブメニューを開かない。
- **マウスの通常右クリック**と**キーボードの `→` 操作**は引き続き有効。
- キーボード起因のコンテキストメニューイベントを一律消費するため、Qtが同じイベントとして扱う `Shift+F10` もLaunch内では無効になる可能性がある。
- ほかのアプリに届くイベントを消費しないよう、Launchに属するウィジェットだけを対象とする。

## Windows実機確認項目

1. Files Listでファイル選択 → `Insert`：緑の選択行が解除され、List/カレントフォルダーが操作対象になる。
2. 続けて `→`：旧ファイルのメニューではなく、カレントフォルダーの背景操作メニューが開く。
3. `Esc` → `↑/↓` → `→`：通常のファイル選択・メニュー操作へ戻る。
4. `Insert` 直後の `Enter` / `F2`：旧ファイルを開く／リネームしない。
5. List／Exp／`/` メニュー／検索欄／Remote でWindows MenuKey：無反応。実マウスの右クリックは従来通り。
6. 日本語IME変換中、インラインリネーム中、ポップアップ表示中でもMenuKeyが余計な操作を起こさない。

## 検証

- Python `compileall`：対象ソースで成功。
- `tests/test_insert_current_folder_menu_disabled_20261121.py`：Qt非依存の挙動テスト。
- `tests/test_slash_menu_key_and_operations_anchor_20261120.py`：11/21仕様に期待値を更新。
- 既存 `/` ナビ・IME・Files関連のQt非依存テストを実行。
- **Windows実機でのGUI確認は未実施**（現在の検証環境にPySide6/Windows GUIがないため）。
