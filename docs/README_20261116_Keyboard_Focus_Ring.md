# FRB Launch — キーボード操作統一・差分パッチ（2026-11-16）

## 基準
`launch_app_20261116_213120.zip`（添付元）のソースを基準に作成。**差分ZIP**なので、プロジェクトルートへ相対パスのまま上書きしてください。

## 改修内容

1. **手裏剣滑走中の Space**：Files Listにキーボードフォーカスがある場合、既存の手裏剣の `_settle()` へ接続し、その場で滑走を停止します。Esc停止も維持。滑走中でないSpaceは従来動作。
2. **Home**：HOMEアイコンと同じ `Launcher.navigate_home()` に接続。既存の滑走を着地させ、Expの第1ルートを選択し、**ExpツリーにQtキーボードフォーカスも移動**。`↓` でそのまま次のフォルダーを選択可能。
3. **Tab／Shift+Tab**：Files画面では次の6地点のみ巡回（逆方向はShift+Tab）。

   `Exp → List → フォルダー検索 → パンくず履歴 → メイン検索 → Browserタブ → Exp`

   Filesタブは巡回に含めません。古いPageルート/ボタンがフォーカスされていても巡回へ合流します。ListからTabで離れるとき、滑走中なら着地。

4. **↓キー**：ExpとListは既存の行選択処理を使用。フォルダー検索にTabで来た場合は検索欄にフォーカスし、最初の↓で既存履歴メニューを表示。その後↑↓で履歴選択、Enterで適用。パンくずの↓はフォルダーお気に入りポップアップ（登録0件でもTabフォーカス自体は可能）、メイン検索の↓は既存の検索履歴を表示。
5. **BrowserタブのEnter**：既存のBrowserタブの `.click()` と同じ処理を使用。
6. **Ctrl+I**：既存の「設定」操作 `open_option_settings()` と同じ処理。

既存のCtrl+F／Ctrl+G／Ctrl+H、PageUp／PageDownの4連打手裏剣、通常のEnter・矢印操作は維持。

## 上書き対象

- `src/app.py`
- `src/expanded_view.py`
- `tests/test_keyboard_shuriken_20261116.py`（Qtフリー擬似キー定義をSpace追加に合わせ更新）
- `tests/test_files_keyboard_tab_ring_20261116.py`（新規）

## テスト

`python -m compileall -q src/app.py src/expanded_view.py`

`python -m pytest -q tests/test_files_keyboard_tab_ring_20261116.py tests/test_keyboard_shuriken_20261116.py tests/test_launch_20261116_ctrl_h_and_chevron.py`

広めの関連テスト：**81 PASS・1 SKIP**。元ZIP内の古い既存テスト（Remote HOMEボタンサイズと旧Expanded keyboardスタブ関係）で5件の失敗があることも、パッチ適用前の原本で再現済み。今回の変更による新規失敗とは分離しています。

## Windows実機での確認

- FilesでHome → Exp先頭の選択 → ↓で次行へ。
- Tab 6回でExpへ戻り、Shift+Tabで逆回転すること。Filesタブを通過しないこと。
- List先頭/途中/空フォルダーからTab → ↓で行選択できること。
- フォルダー検索にTab → ↓で履歴表示 → ↓で履歴選択 → Enterで検索適用。
- パンくずにTab → ↓で登録フォルダー選択、メイン検索にTab → ↓で履歴表示。
- BrowserタブにTab → EnterでBrowserを表示。
- PageDown 4連打 → Spaceで着地、再度4連打 → HomeでExp先頭へ戻ること。
- Ctrl+Iで設定画面が開くこと。

**注意**：この環境にはPySide6/Windows GUIがないため、実画面のキーボード操作は未検証です。テストはソース上の責務呼び出し・状態遷移を検証しています。適用前に現行ソースのバックアップを残してください。
