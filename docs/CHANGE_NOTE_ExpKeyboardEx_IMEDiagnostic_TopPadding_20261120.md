# FRB Launch / Exp Keyboard Ex — IME診断ログ＋操作メニュー先頭余白

基準: `launch_app_20261120_225817.zip`（2026-11-20）

## 変更1：操作メニューの一行目の上余白を増やす

- Files Exp/List の操作コンテキストメニュー `QMenu#frbFilesContextMenu` に対して、上余白を従来 5px → 9px にする設定を追加。
- 「Exp列へ戻る」「List列へ進む」とメニュー上枠の距離が窮屈にならないようにする。
- 左右／下の余白、各メニュー行の高さ・内容・色・角丸・影は変えない。
- 他のウィンドウ用コンテキストメニュー、Exp Keyboard Ex の探索メニューも変えない。

## 変更2：日本語IMEイベント調査（通常時OFF）

前回の改善後もExp Keyboard Exで日本語入力できないため、動いている既存のCascadeMenuと同じ実行時に比較可能なログを追加した。**今回はIMEの動作修正ではなく、原因調査を行うための診断版。**

- `src/slash_ime_trace.py`: フォーカス移動、キー、InputMethod、InputMethodQuery、ウィンドウの表示／非表示、IMEロケールのメタデータを取得。
- `src/slash_exp_navigation.py`: Exp Keyboard Exの検索ボックスとメニューを診断対象へ追加。フォーカス要求とIME転送を記録。
- `src/app.py`: 既存CascadeMenuの日本語入力できる検索ボックスを比較対象へ追加。
- 既定で **OFF**。`FRB_SLASH_IME_TRACE=1` を設定した場合だけログを作成。未設定時はQtの監視フィルタを追加しない。
- **日本語の入力文字列・変換文字列・パス・ファイル名・クリップボードの内容は記録しない。**文字数、イベント種別、キー識別番号、フォーカス状態だけ記録。
- Qtイベントの診断フィルタは処理を横取りせず、常に `False` を返す。

## Windowsでの採取手順

1. 差分ファイルをLaunchフォルダーに上書きし、**既存Launchをトレイも含めて完全終了**する。
2. `diagnose_exp_keyboard_ime.bat` をダブルクリック（`.venv\Scripts\python.exe` 必須）。**既存EXEで起動しないこと**。
3. Keyboard Exで `/` → 検索欄に日本語（例: あ）を入力／変換／確定する。できない状態でも続行。
4. 通常のCascadeMenuでも同じ日本語入力を試す（正常系の比較）。
5. Launchを完全終了すると診断ログがメモ帳で開く。ログをチャットへ添付。

ログ保存先：`%TEMP%\FRBLaunch\exp_keyboard_ime_trace.log`

診断バッチは開始時に旧ログを消して新規採取する。個人の入力文字列は記録しないが、アプリ内のフォーカス状態などの診断情報は含まれるので、共有前に内容を確認できる。

## 変更ファイル

- `src/launch_appearance.py`
- `src/slash_ime_trace.py`（新規）
- `src/slash_exp_navigation.py`
- `src/app.py`
- `diagnose_exp_keyboard_ime.bat`（新規）
- `tests/test_slash_ime_diagnostics_and_operation_padding_20261120.py`（新規）

## 確認事項

- Linuxのテスト環境ではWindowsの日本語IMEを再現できない。
- 構文・既存のメニュー関連テストは実施するが、IME原因の確定は実機ログ後。
