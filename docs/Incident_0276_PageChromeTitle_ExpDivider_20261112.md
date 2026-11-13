# FRB Launch incident 0276 — Page登録・Chromeタイトル・Exp区切り線

基準ZIP：`launch_app_20261112_154219.zip`。差分ZIP形式。Studio側のソースは変更しない。

## Expected / Actual / Diff

| 対象 | Expected | 修正前の問題 | 実装 |
|---|---|---|---|
| Chrome URLドロップ | URLとともに提供されたページタイトルでブックマーク登録する | 先頭で取得したURLだけが残り、HTML/Windows仮想ショートカット側のタイトルが捨てられる | `mime_sources` 内で同じURLのMIME表現を統合してタイトルを優先。URLしか得られない場合は従来フォールバックを維持 |
| Page直下へ既存ファイル登録 | Page直下にJSON登録可能。Exp列には表示せず、List列には表示 | Pageメニューだけ既存ファイル登録を禁止 | 既存 `_add_registration_menu_actions` の `allow_file=True` と既存 `virtual_exp_folders` / `virtual_list_rows` を利用 |
| Page行の右クリック | 「Pageを追加...」を選べる。作成先はPage階層の兄弟 | Exp余白メニューからしか追加できない | 共通 `_add_page_creation_menu_action` をExp余白とPage行から呼ぶ |
| Exp列区切り線 | 区切り線の上下に余白。PCは他の行と同じ高さで、PCの下に余白を作らない | PC行のサイズを増やすことで、余白がPCの下にも生まれる | PC直前に描画専用の操作不可行を挿入し、その行に区切り線を描く。HOME・ホイール・Remoteは装飾行を無視 |

## 守るべき不変条件

- 物理ファイル・フォルダーの操作は行わない。設定JSONへの追加はStudio Change Coreで実施する。
- Page直下のファイルはExpに登場しない。Listへの投影のみ。
- URLは重複登録せず、URL本体は `launch_target` にそのまま保持する。
- Pageの追加は既存Pageの子にしない。StudioのPage Addを利用する。
- `PC` や物理フォルダーの通常行高・表示・矢印・選択は変えない。
- 区切り線は `NoItemFlags` で非選択・非操作。Remoteとホイールでスキップする。
- 保留の「←で設定JSONフォルダーに戻る」仕様には触れない。

## 検証

Linux／Python 3.13のユニットテストに加え、`FRB_STUDIO_TEST_ROOT` を指定してStudio CLI実接続のPage Addとファイル登録を検証。

```powershell
python -m pytest -q tests/test_chrome_title_and_exp_separator_20261112.py tests/test_page_and_chrome_drop_20261112.py tests/test_page_root_file_registration_20261112.py tests/test_exp_pc_decorative_divider_qt_20261112.py
```

**Windows受入（必須）：**

1. Expの区切り線上・下に空間があり、**PCの下には不自然な空間がない**。区切り行はホイールやリモコンでも選ばれない。
2. Page行の右クリックから「Pageを追加...」。作ったPageが独立する。
3. Page行の右クリックから「既存ファイルを登録...」。追加アイテムが**Listだけ**に登場する。
4. ChromeアドレスバーのURLを設定JSONフォルダーへドラッグし、タイトルが取得できるケースでURLそのままではなくページタイトルで登録される。

PySide6がない環境ではGUIテストはSKIP。Windows画面上の見栄え・ドラッグ・ぐりぐりの最終合格は未確認。
