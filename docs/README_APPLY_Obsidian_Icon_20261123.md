# FRB Launch / `.md` Obsidian文書アイコン 再チャレンジ差分

変更内容：Windowsの有効な`.md`関連付けの**文書専用アイコン**を優先表示します。ファイル用のアイコン設定・拡張子だけから取る方式・Qtの順にフォールバックします。

## 適用

1. Launchを完全終了（タスクトレイも）。`src/app.py`、`src/file_icon_policy.py`、`src/windows_file_association_icon.py`をバックアップ。
2. このZIPの`src/`配下3ファイルをLaunch本体の同名ファイルへ上書き。
3. Python実行版なら再起動。exe版なら `_build_windows.bat` 等でexeを再ビルド。
4. エクスプローラーでObsidianの紫色文書アイコンが表示されている`.md`をLaunchのFiles Listと比較。

`tools/` と `tests/` のファイルは動作確認用。`docs/`のCHANGE_NOTEに詳細あり。

## 紫色にならないとき

```powershell
.venv\Scripts\python.exe tools\probe_markdown_document_icon.py --png
```

このコマンドはWindowsの有効な関連付け先、登録文書アイコン、ファイル種類だけのアイコンを比較し、必要ならPNGを作る。`--file "C:\...\xxx.md"`を付ければ実ファイル由来のアイコンも比較できる。

**注意**：Windows実機での目視確認はこの環境では未実施。関連付けがObsidian以外なら紫色の強制表示はしない。設定JSONと既定のアプリは変更しない。

回帰テスト：**37件PASS**（Python/静的テスト）。
