# FRB Launch / Exp Keyboard Ex — アイコン位置・起動フォーカス・Enter着地

ベース：`launch_app_20261120_205025.zip`（2026-11-20）

## 変更点

1. **メニューのアイコン左端を通常／長い一覧で揃える**
   - `src/launch_appearance.py`
   - スクロール時の `QTreeWidget` は装飾用の余白を既に持っているため、追加していた `padding-left:15px` を `0px` に変更。
   - 通常の `QMenu` のレイアウトは維持。通常の右クリックコンテキストメニューは変更なし。
   - 短いメニュー／長い一覧でアイコン開始位置が大きく変わる症状への対処。

2. **Launch.exeをダブルクリックした際のキーボード受付**
   - `src/app.py`
   - 既存インスタンスへのIPC表示依頼／`--preview`での初期表示に、既存の `restore_keyboard_focus()` を使うフォーカス再取得を追加。
   - 最初と120ms後のフォーカス復帰。呼び出し時・表示後の前面ウィンドウだけを許可し、その後別アプリが前面に来た場合は奪わない。
   - デスクトップ壁紙のダブルクリック操作に既存の専用制御があるため、それは変更なし。

3. **Exp Keyboard ExのフォルダーEnterでList一行目へ着地**
   - `src/slash_exp_navigation.py`
   - Exp側／List側のどちらから `/` を開始しても、現在フォルダー・子フォルダー・仮想フォルダー・PCのEnter成功後、List欄へフォーカスを移し、先頭の有効行をカレントにする。
   - 空フォルダーは行を選べないがList欄へフォーカス。
   - ファイル／URL／コンテキストコマンドのEnterには適用しない。
   - QMenuのネイティブキーボードグラブが解除されてからフォーカス変更。

## 非変更

パンくず論理パス、緑背景フォルダー拡張、`/`トグル、Right/Left、表示位置、メニュー高さ、ライト／ダーク配色、角丸、枠線は変更なし。

## テスト

- `python -m pytest -q tests/test_slash_exp_navigation_20261118.py tests/test_slash_exp_keyboard_ex_breadcrumb_20261120.py tests/test_slash_exp_keyboard_ex_selected_folder_height_20261120.py tests/test_slash_exp_frame_border_20261120.py tests/test_slash_exp_icon_inset_20261120.py tests/test_slash_exp_icon_and_focus_20261120.py tests/test_windows_focus.py tests/test_cascade_initial_keyboard_focus_20261021.py tests/test_launch_20261116_five_keyboard_changes.py`
- 結果：**93 PASS**、Python構文チェックPASS。
- 広めのテストでは **107 PASS / 8 FAIL**。8件は元ZIPでも **101 PASS / 8 FAIL** と同一の既存失敗（古い色・アンカー期待値6件とPySide6未導入2件）。追加6件はいずれもPASS。

### Windows上での確認事項（必須）

- `.vscode` のように項目の少ないフォルダーと `articles` のように長い一覧の両方でアイコン左位置を見る。
- Launchがすでに常駐しているとき、`Launch.exe` をダブルクリックで再表示して矢印キーや `/` がクリックなしで反応するか。
- Expから `/`→子フォルダーEnter、Listから `/`→子フォルダーEnter、`（カレントフォルダー）` Enter で List 先頭行が選ばれ矢印操作できるか。
- Windows / PySide6 の実描画とネイティブフォーカスはこのLinux環境では直接確認できていない。

## 適用

添付差分ZIP内の `src/` と `tests/` と `docs/` をLaunchアプリのルートへ上書き。ユーザー設定JSONは含まない。
