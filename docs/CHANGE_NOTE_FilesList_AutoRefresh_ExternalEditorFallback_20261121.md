# FRB Launch — Files List自動更新／外部エディター未導入時フォールバック（2026-11-21）

正本: `launch_app_20261121_111704.zip`

## 変更内容

1. **Files Listを表示中の実フォルダーだけ監視**
   - `QFileSystemWatcher.directoryChanged` でExplorerなどによるフォルダー内の作成・削除・名前変更を検知。
   - 300msのデバウンス後、既存の `refresh_current_directory()`（F5処理）を再利用する。
   - 監視先は表示中の物理フォルダー1件。Exp列や仮想Launch JSONフォルダーは監視・書き換えしない。
   - フォルダー移動後の遅延通知は破棄。手動F5も継続。
   - 検索条件、可能な範囲で選択行、スクロール位置を維持。リネームにより旧名称が消えた場合は、直前の行番号に近い行を暫定カレントにする（ファイル個体の同一性追跡ではない）。
   - List内インライン名前変更中、ドラッグ中、ファイル操作ダイアログ中は更新を延期。非表示中の通知は表示復帰時に再試行。
   - ファイル索引SQLite、Launch登録JSON、履歴、F5ボタン、Expの開閉状態は変更しない。

2. **専用エディター未導入環境で外部起動にフォールバック**
   - 物理Files Listの `.md` (Obsidian)、VS Code向けファイル、`.txt/.ini` (サクラエディタ) は従来ルートを維持。
   - 専用エディターの実行ファイルが見つからない場合、第三列埋込は試さず、`os.startfile(対象ファイル)` でWindowsのファイル関連付けに委譲する。
   - サクラが見つからない `.txt/.ini` は既存の一般起動経路をそのまま使用。
   - 検出後にアンインストールされた場合など `FileNotFoundError` でも既定アプリへフォールバック。アクセス拒否など別種の起動エラーは握りつぶさない。
   - Studio管理対象JSONの優先規則、実行アクション、関連付け・設定ファイルの内容は一切変更しない。
   - 既定アプリが存在しない／Windows関連付けが壊れている場合は従来のエラー通知を出す。

## テスト

- 新規 `tests/test_files_list_autorefresh_editor_fallback_20261121.py`: **10 PASS**。
- 既存関連セット + 新規: **78 PASS / 18 FAIL**。既存のみ正本比較: **68 PASS / 同じ18 FAIL**（今回の新規FAIL 0）。
- Python構文検査 PASS。
- Linux側ではPySide6とWindows実機がないため、**実際のWindows `QFileSystemWatcher` 通知とファイル関連付けの起動は未検証**。

## Windows実機の確認例

1. Launch Files Listでローカルの任意フォルダーを開き、Explorerで同じフォルダーの `old.txt` を `new.txt` に変更。数百ms後、Listに新名称が現れ、F5不要かを確認。
2. カレント行・スクロール位置、検索中、Exp移動、インラインF2編集の途中に勝手な更新が起きないか確認。
3. 別のフォルダーへ移動し、古いフォルダーで名前変更しても現在のListに反映されないことを確認。
4. Obsidian/Code/Sakuraが見つからないテスト用PCでは、対応する既定アプリで外部起動することを確認。特に `.py` / `.ps1` 等の既定アプリが実行系に関連付いている環境ではテストファイルを安全な内容にすること。
5. 専用エディターがインストール済みなら、その既存起動経路が維持されることを確認。

## 含まれる差分ファイル

- `src/expanded_view.py`
- `src/external_preview_route.py`
- `tests/test_files_list_autorefresh_editor_fallback_20261121.py`
- 本変更メモ
