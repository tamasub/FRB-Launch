# FRB Launch — Files List フォルダー検索 Escクリア（2026-11-17）

## 変更内容

- Filesモードの「Files List」フォルダー検索欄（`middle_search`）にフォーカスがあり、検索文字がある場合、単独 `Esc` で入力をクリアする。
- 標準の「×」ボタンと同じ `QLineEdit.clear()` を使用するため、既存の `textChanged → apply_middle_filter` で一覧が再描画される。
- クリア後も検索欄のフォーカスはそのまま維持する。
- 検索欄以外、Browserモード、検索欄が空の場合の `Esc`、Ctrl+G／Ctrl+H履歴操作は変更しない。

## 差分

- `src/expanded_view.py` : Escの条件付きクリア処理を追加、`eventFilter` に接続。
- `tests/test_files_list_search_escape_clear_20261117.py` : Qtに依存しない動作契約5件のテストを追加。

## 検証

- `python -m py_compile src/expanded_view.py`: 成功。
- `PYTHONPATH=src pytest -q tests/test_files_list_search_escape_clear_20261117.py tests/test_ctrl_gh_history_open_immediately_20261117.py`: 9 passed。
- Windowsの実GUI（PySide6）はこの環境で動作確認できないため、手元で `*.md` → Esc → 全件再表示を確認してください。

## 適用

FRB Launchのルートに、この差分ZIP内の相対パスを維持して上書きしてください。元データや設定JSONは含みません。
