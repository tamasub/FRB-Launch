# Studio 3列目プレビュー再オープン時の QTimer 修正

- 基準：`launch_app_20261118_184303.zip` + SilentDock 差分
- 症状：`_ensure_studio_preview` で `UnboundLocalError: cannot access local variable 'QTimer'`。
- 原因：初回表示分岐の `from PySide6.QtCore import QTimer` が、メソッド全体の `QTimer` をローカル変数にする。次回表示時は初回分岐を通らず、分岐外の `QTimer.singleShot` で例外。
- 修正：同メソッド内の条件付きローカルimportを削除。ファイル先頭に既存の `QTimer` importを再利用。
- 対象：`src/expanded_view.py`。Studio側は今回変更なし。Silent Dock の既存機能は維持。
- 検証：GUI非依存テストで、既に第3列が表示されている状態の `_ensure_studio_preview()` を直接実行。Windows実機GUIでの表示は未検証。
- 補足：一瞬ウィンドウが見える現象とChromium SQLiteキャッシュ警告は今回の修正対象外。
