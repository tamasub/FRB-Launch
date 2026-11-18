# FRB Launch — Files Exp右クリック・コンテキストメニューのキー操作

日付: 2026-11-18

## 症状
Files Expのフォルダーを右クリックしてメニューを開いたあとも、キーボードの↑↓やEnterをExp本体が受け取り、メニュー選択・実行ができない。

## 原因
Files Exp/Listコンテキストメニューは、Remote（ぐりぐり）とマウスの共存のため非モーダル `Qt.Tool` として表示する。実際のキーボードフォーカスは元のExpツリーに残る。

アプリケーション共通の `RemoteContextWheel.eventFilter()` には `UP/DOWN/LEFT/RIGHT/ENTER/ESCAPE` のキー変換が実装済みだが、`_frb_keyboard_opened` が設定されている場合にだけ有効になっていた。従来はキーボードから開くListメニューやSettingsなどに限定され、マウスから開いたExpメニューでは有効ではなかった。

## 対応
共通コンストラクター `FRBContextMenu` で `_frb_keyboard_opened = True` を設定。Exp/Files List（ヘッダー・背景を含む）の右クリックメニューが既存の共通Runnerを利用できるようにした。

- ↑↓: 有効な項目を選択（従来のぐりぐりRunnerと同じラップ動作）
- →: 選択中のサブメニューを開く
- ←: サブメニューから戻る。ルートでは閉じる
- Enter: 選択中の項目を実行（メニューの子階層では展開）
- Esc: メニューを閉じる
- 既存のマウスクリック／ホイール選択と実行処理は変更なし

メニューが閉じるとRunnerはアプリケーションのイベントフィルタを解除し、キーは元のExpへ戻る。

## 検証
`python -m pytest -q tests/test_files_exp_right_click_keyboard_20261118.py`

GUI実機確認（Windows）: Expのフォルダーを右クリック → ↑↓ → Enter、サブメニュー →／←、Escでキャンセル、閉じた後のExpキーボード移動、マウスによる選択／ホイール操作を確認。
