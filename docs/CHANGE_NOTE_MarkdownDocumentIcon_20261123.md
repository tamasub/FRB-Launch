# FRB Launch — Markdown（Obsidian）文書アイコン再挑戦

更新日：2026-11-23  ／ 対象：Files Exp / Files List / 登録済みLaunch設定JSON

## 現象

- エクスプローラーの`.md`はObsidianの紫色系アイコンなのに、Launchでは汎用紙アイコンになる。
- 16×16pxへの変更によりExcel/TXTは改善。今回はサイズを変えない。

## 原因仮説と今回の変更

従来は`SHGetFileInfoW('.md', SHGFI_USEFILEATTRIBUTES)`だけで拡張子に対応するアイコンを問い合わせていた。しかしWindows Shellには**拡張子の一般的なアイコン**と**現在の既定アプリが登録した文書専用アイコン**の違いがある。後者が優先されていなかった可能性がある。

### `.md`のみの取得順

1. Windowsの有効な関連付けから`AssocQueryStringW(ASSOCSTR_DEFAULTICON)`を問い合わせる。
2. 登録された文書用アイコン資源（`.exe`/`.dll`/`.ico`とインデックス、負数のリソースIDも含む）を`SHDefExtractIconW`で取得する。
3. 失敗時は**実在パスが登録されていれば**`SHGetFileInfoW(path)`（`SHGFI_USEFILEATTRIBUTES`なし）を試す。
4. さらに失敗し、**現在の既定アプリがObsidian.exeと確認できた場合に限り**、その実行ファイルのアイコンを試す。
5. 最後は従来の拡張子取得／Qtアイコンへ戻す。

Windowsに関連付けアプリの変更は行わず、Obsidianのexe/ロゴを強制表示もしない。`.md`以外のファイル種類・独自のアイコン・フォルダー色・URLはそのまま。

## 変更ファイル

- `src/windows_file_association_icon.py`：Windows登録文書アイコン取得と確実なフォールバック
- `src/file_icon_policy.py`：仮想行へ`_file`を追加せず、登録済みOpenターゲットの参照だけ取得する`icon_source_path`
- `src/app.py`：`.md`の表示用パスをShellに渡し、パス単位のフォールバックをキャッシュ（サイズ16px維持）
- `tests/test_windows_shell_association_icons_20261123.py`：既存回帰テスト更新
- `tests/test_registered_json_filetype_icons_20261123.py`：既存回帰テスト更新
- `tests/test_markdown_registered_document_icon_20261123.py`：新規ケース8件
- `tools/probe_markdown_document_icon.py`：**Windows上だけ**で利用する診断用コマンド（読み取り専用）

## 動作確認

Linuxの静的・Python回帰試験は37件PASS。Windows実機の表示結果は未確認。

Pythonソース実行の場合は変更したsrcを上書きしてLaunch完全終了→再起動。exe版の場合は再ビルドが必要。

```powershell
python -m pytest -q tests/test_windows_shell_association_icons_20261123.py tests/test_markdown_registered_document_icon_20261123.py tests/test_cloud_filetype_icons_20261026.py tests/test_registered_json_filetype_icons_20261123.py tests/test_launch_virtual_explorer_split_20261103.py tests/test_launch_0269_page_root_file_drop_20261111.py
```

Windows実機でなお紫にならなければ、以下を**Launch作業フォルダーから**実行し、出力を比較する。

```powershell
.venv\Scripts\python.exe tools\probe_markdown_document_icon.py --file "F:\FRB_Apps\FRB_Launch\docs\frblaunch_memo.md" --png
```

※上記パスは画像に登場した例。ローカルの実際の`.md`ファイルに合わせて適宜置換する。`--file`を省いても実行可能。生成PNGは作業フォルダーに保存される（`--png`指定時のみ）。端末出力にはユーザー名・パスが含まれる場合がある。

## 非対象

- `.md`をObsidianで開く既定アプリの設定変更
- `Launch`側のJSONデータへの書き込み
- Obsidian起動／ドッキング／プレビュー挙動の変更
- ファイル監視の追加
