# FRB Launch 0283 — Windowsビルド前GUIスモーク検査の誤判定対策

## 報告された事象

- FRB StudioのNativeShell publishは成功している。
- 新しい `F:\FRB_Apps\FRB_Launch` の `_build_windows.bat` は、PyInstaller実行前のGUIスモークで停止。
- ログ：`FAIL FRBContextMenu GUI smoke: Exp: missing visual foreground: icon=256, label=0`。
- `icon=256` は固定16x16マゼンタのテスト用アイコンが描画されていることを示す。
- `label=0` は「決め打ちのRGBしきい値・検査範囲で文字ピクセルを数えられなかった」という意味で、必ずしも実画面上で文字が消えていることを証明しない。

## 原因分析と対策

従来の `scripts/smoke_context_menu_native_gui.py` は、QMenuスクリーンショットのコピー行に対し `red < 145, green < 145, blue < 145` かつ x=67..205 の画素を数えていた。Qt/Windowsの描画条件・色・文字位置に依存する。

0283では実描画QMenuのアイコンが存在することを確認したうえで、**同じQActionの文字列だけを「コピー」から同じ3文字の「ラベル」に差し替えた前後の画像**を比較。アイコンの領域は除外し、行位置・画像サイズが変わらない場合にのみ、テキスト領域で十分な画素差分が出ることを合格条件とした。

文字列の差分が実描画に現れない場合は、従来どおりビルドを中止する。`_build_windows.bat` の安全ゲートは無効化していない。

## 失敗時の追加証拠

以下の2枚を `F:\FRB_Apps\FRB_Launch` に保存：
- `context_menu_smoke_failure_exp.png` : 元のコピー表記
- `context_menu_smoke_variant_exp.png` : コピーをラベルに置き換えた表記

FAILメッセージには `dark_label`（旧画素判定値）、`text_diff`（新しい判定値）、`geometry_same` を表示。もしまだFAILする場合はこの2枚の画像で実際の文字欠落かどうかを判断する。

## 実行手順

1. 既存の `F:\FRB_Apps\FRB_Launch` に差分を上書き（設定JSONは変更しない）。
2. Windowsの同フォルダーで `.venv\Scripts\python.exe scripts\smoke_context_menu_native_gui.py` を単独実行する（PyInstallerの時間を使わずに判定できる）。
3. Exp/ListともにPASSなら `_build_windows.bat` を実行する。
4. FAILなら追加される2枚の画像を確認する。GUIの本当の前景不具合が起きていれば、その場でビルドを止めるのが正しい。

## 検証記録

- ローカルで `tests/test_context_menu_pixel_probe.py` 4件PASS。
- 関連する非GUIテスト合計14件PASS。
- `scripts/check_dialog_contract.py` と `scripts/check_context_menu_contract.py` PASS。
- GUI実描画テストはWindows/PySide6環境での実行が必要。ここではWindowsの描画結果は未検証。

## ビルド時間について

新しい `F:\FRB_Apps\FRB_Launch` に移動すると `.venv` を新設・再準備する可能性があり、依存パッケージ確認で初回は時間が増える。また現行ビルドはGUIスモーク後に `PyInstaller --clean` を実行する。今回のログではGUIスモークで止まっており、その時点でPyInstallerは未実行。
