# FRB Launch ぐりぐり丸ボタン描画エラー修正（2026-11-15）

## 適用対象

前回お渡しした `FRBLaunch_Guriguri_Rail_RoundButton_Split_Diff_20261115.zip` を適用したソース。
本ZIPは追加修正分です。`src/` と `tests/` を **FRB_Launch のソースルートへ上書き展開**してください。既存の設定データは変更しません。

## 修正

- `src/launch_remote.py`: `PySide6.QtCore.QPointF` のインポート不足を解消。
- 同ファイルの `RoundRailWheelPad.paintEvent`: `QPainter` の終了を `try/finally` で保証。描画で例外があっても `end()` が呼ばれます。
- 円の位置、線幅、左右領域判定、長押し抑止、4択設定は変更していません。

## 期待される結果

- 起動時・再描画時の `NameError: name 'QPointF' is not defined` が発生しなくなる。
- 丸ボタンに「ぐりぐり」、中央の縦点線、「Exp」「List」と選択側の点が表示される。
- 今回の原因に起因する `QBackingStore::endPaint()` の警告も解消する見込み。

SQLiteの `Invalid total_dict_size` やGoogleページの preload 警告は別系統のログで、本修正の対象外です。

## 検証

- `python -m pytest -q tests/test_round_rail_paint_crash_fix_20261115.py tests/test_round_rail_wheel_split_20261115.py tests/test_remote_display_four_modes_20261115.py tests/test_tonton_lane_wheel_hybrid_20261115.py tests/test_files_tonton_lane_single_click_20261115.py` → **25 passed**。
- 描画メソッドそのものを簡易Qt環境で呼び、線と3つの文字描画・正常終了を確認。描画中に例外を発生させても `QPainter.end()` が呼ばれることを確認。
- Python構文チェックPASS。Windows + PySide6の実GUI描画・入力は未検証。
