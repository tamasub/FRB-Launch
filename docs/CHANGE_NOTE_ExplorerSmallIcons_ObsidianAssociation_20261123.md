# FRB Launch — Explorer相当16pxアイコンと .md関連付け表示

更新日: 2026-11-23

## 現象・再現

Files Exp / Files ListのファイルアイコンがWindowsエクスプローラーの詳細表示より一回り大きく、一部のTXTなどで外周が窮屈に見える。また、エクスプローラー側ではObsidianアイコンであるMarkdown（`.md`）が、Launchでは汎用ファイルアイコンになる。

## 原因

- `src/expanded_view.py` の共通 `ExpandedPanel` のツリーは、各行のアイコンを19×19で描画していた。エクスプローラーの詳細表示に合わせるなら16×16が適切。
- `src/app.py` の `Launcher.row_icon` は拡張子ごとのアイコン取得に `QFileIconProvider(QFileInfo('FRBLaunchTypeSample' + extension))` を使用していた。存在しないサンプル名ではQtが汎用アイコンを返す場合があり、Windowsのユーザーごとの関連付けアイコン（例: `.md` → Obsidian）を忠実に表示できない。

## 改修

1. `src/expanded_view.py`：Files Exp / Files Listが共用する `ExpandedPanel.tree` のアイコンを **19×19 → 16×16** に変更。行高・行選択・スクロール・右側の展開操作は変更しない。
2. `src/windows_file_association_icon.py`（新規）：Windowsの `SHGetFileInfoW`（`SHGFI_ICON | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES`）から拡張子の関連付けアイコンを取得。`HICON` を32bit DIBへ描画してQtの `QIcon` へ変換する。ハンドルは解放する。対象の実ファイルは開かない。
3. `src/app.py`：`Launcher.row_icon` の `source == 'type'` でWindows Shellアイコンを優先。利用できない場合は従来の `QFileIconProvider` へ戻る。アイコンは既存の拡張子別キャッシュで再利用。

## 維持する仕様

- JSONの登録データ、ドラッグ＆ドロップ、実行パス、仮想ファイル判定は変更しない。
- フォルダー色、URL、手動アイコン、アプリ/ショートカット/ICOのパス固有アイコンは変更しない。
- Windowsの関連付けアプリがObsidianなら`.md`はObsidian相当のアイコンとなる。ObsidianをLaunch側で強制指定するわけではない。
- Windows以外やWin32アイコン取得に失敗した場合は従来の表示に戻る。アイコン取得の失敗でFiles Listを停止させない。

## 差分ファイル

- `src/app.py`（差し替え）
- `src/expanded_view.py`（差し替え）
- `src/windows_file_association_icon.py`（新規）
- `tests/test_windows_shell_association_icons_20261123.py`（新規）
- `docs/CHANGE_NOTE_ExplorerSmallIcons_ObsidianAssociation_20261123.md`（本書、新規）

## テスト

```powershell
python -m pytest -q tests/test_windows_shell_association_icons_20261123.py tests/test_cloud_filetype_icons_20261026.py tests/test_registered_json_filetype_icons_20261123.py tests/test_launch_virtual_explorer_split_20261103.py tests/test_launch_0269_page_root_file_drop_20261111.py
```

結果: **29 passed**（Linux、Pythonロジックテスト）。

旧UI関連8ファイルのテスト群は **14 failed, 43 passed** だったが、添付最新版の **修正前** にも同じ **14 failed, 43 passed** を確認。主な原因は、UI構造の変遷で古くなった期待文字列や、ZIP未同梱のユーザ設定JSON。今回の修正で増加した失敗ではない。

この環境はWindows/PySide6実機描画を検証できないため、Win32アイコン取得・Obsidianの見え方はWindows実機で確認が必要。

## Windowsでの確認

1. 適用前に既存の `src/app.py` と `src/expanded_view.py` をバックアップ。
2. 差分ZIPの `src/` を同じ構成のフォルダーへ上書きし、`windows_file_association_icon.py` を追加。Launchを完全終了→再起動。exeを使用している場合はexeを再ビルド。
3. WindowsエクスプローラーとLaunchで同じ `Documents` フォルダーを表示。TXT/Markdown/Excelのファイルアイコンが共に16pxになり、端が切れていないことを確認。
4. `.md` の関連付けがObsidianなら、エクスプローラーのObsidian系アイコンと一致するか確認。
5. 設定JSONにドロップ登録したファイル、フォルダー色、URL、手動設定アイコンが変わっていないことを確認。
