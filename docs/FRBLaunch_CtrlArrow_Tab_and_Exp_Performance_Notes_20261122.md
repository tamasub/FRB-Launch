# FRB Launch — 右手操作 キー人事異動／Exp応答性メモ

## 基準

直前に作成した `FRBLaunch_RightHand_RoundCorners_ClockwiseTab_20261122_diff.zip` を適用した状態。
最新版アップロード `launch_app_20261122_164928.zip` に対する前回の差分の**追加差分**。

## 今回実装

- テンキー **1** のTab割当を全面廃止。**ダイアログ内を含めて**、テンキー1は通常どおり入力・操作できる。
- **Ctrl + →** = Tab（次のフォーカス対象へ）
- **Ctrl + ←** = Shift + Tab（前のフォーカス対象へ）
- Files画面では、通常Tabと同じ時計回りの巡回順を維持：メイン検索 → パンくず → フォルダ検索 → List → Exp → （Browserがある場合はBrowser） → メイン検索。
- ダイアログでは既存のQt Tab/Shift+Tabによる項目間移動へ接続。
- 小指Zero（テンキー0）によるEnter、Menu、Ctrl+Menu、および本来のTab/Shift+Tabは変更なし。
- Launchの管理するウィンドウ内だけでキーを扱い、他アプリのキー操作は変更しない。

**注意：** Launchのテキスト入力欄では、Ctrl+←/→の本来の単語単位カーソル移動はTab巡回に置き換わる。入力中の数字「1」は奪わない。

## Exp矢印キーの重さ（相談調査のみ、今回は修正なし）

`src/remote_files_explorer.py` 現行の仕組み：

- `self._selection_timer.setInterval(130)`：Expで選択を移した後、130ms静止したらFiles List/パンくずを更新。矢印入力そのものの遅延ではない。
- `self._tree_state_timer.setInterval(350)`：選択・スクロール等のツリー状態を後から記録。
- `self.tree.setAnimated(True)`：ツリー展開・折畳みにアニメーションが入る。
- `self._visible_watch_timer.setInterval(100)`：表示範囲のフォルダー監視対象更新。
- `self._visible_refresh_timer.setInterval(1000)`：フォルダー内容の変更検知更新。

### 次の試行案（未実装）

1. **選択行の反応は速いがFiles Listの表示更新が引っかかる場合**：130msを180～220msに変え、連打中の更新回数を減らせるか測る（静止後の反映はその分遅くなる）。
2. **展開/折り畳みそのものがもたつく場合**：`setAnimated(False)`を先に比較する。
3. **キー自体が重い場合**：1キーあたりの選択処理・UI再構築・ディスクアクセス時間を計測し、遅延値だけで対処しない。

## 差分ファイル

- `src/finger_zero_keys.py`
- `src/expanded_view.py`
- `tests/test_finger_zero_20261122.py`
- `tests/test_finger_zero_ui_bridge_20261122.py`

## 自動検証

`python -m compileall -q src/finger_zero_keys.py src/expanded_view.py`

`python -m pytest -q tests/test_finger_zero_20261122.py tests/test_finger_zero_ui_bridge_20261122.py tests/test_files_keyboard_tab_ring_20261116.py tests/test_launch_action_menu_20261122.py tests/test_insert_current_folder_menu_disabled_20261121.py tests/test_slash_menu_key_and_operations_anchor_20261120.py tests/test_files_exp_right_click_keyboard_20261118.py`

- 48件PASS（Qt非依存の関連テスト）。
- PySide6は現行のLinux検証環境にないため、Windows GUI実動作・入力メソッドは未確認。
- 古い `test_exp_debounced_live_list_preview_20261103.py` は、未変更の既存コードでもfixtureが現在の実装に追従しておらず失敗するため今回のPASS件数に含めていない。

## 実機確認

1. Files画面で検索欄からCtrl+→を押すとパンくず、さらにフォルダ検索→List→Expへ進むこと。
2. Ctrl+←で逆に移動すること。
3. 設定/編集などのダイアログの文字・数値欄でもCtrl+→/←で次／前の項目へ移動すること。
4. ダイアログの数字入力欄でテンキー「1」を押して数字が入力されること。
5. 既存のMenu・Ctrl+Menu・テンキー0・通常のTabキーがそのまま動くこと。
