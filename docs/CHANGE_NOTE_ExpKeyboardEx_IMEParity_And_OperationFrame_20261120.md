# FRB Launch — Keyboard Ex IME / 操作メニュー二重輪郭修正

2026-11-20

## 適用基準
- `launch_app_20261120_215139.zip` に `FRBLaunch_ExpKeyboardEx_OperationsIME_20261120_diff.zip` 適用済みの状態
- 今回の差分は `src/slash_exp_navigation.py` と `src/launch_appearance.py` のみ

## 1. Keyboard Ex の日本語IME（Windows）

既存の `CascadeMenu` は日本語IMEで入力できる。そこで、Keyboard Ex のQMenuにも同じ「メニュー自身がIME入力可能なことを返し、OSの入力方式イベントを編集欄へ渡す」契約を採用。

- `SlashExpMenu.inputMethodQuery(ImEnabled)` で `True` を返す。
- 初期フォーカスはメニューへ（従来CascadeMenuの方式に合わせる）。通常文字は既存の検索欄へ送る。
- Windowsから届く `QInputMethodEvent` を `QLineEdit` へ渡し、ひらがな・漢字変換のpreedit/commitをQtに処理させる。
- 変換中にメニューに届いた矢印・Enter・Escで階層操作を起動しない。
- クリックした編集欄では引き続きQLineEditが直接IMEを処理する。

※Windows実機のIMEはこの実行環境では利用できず、試作のため実機確認が必須。

## 2. 通常の青白い操作コンテキストメニューの二重枠

- `QMenu#frbFilesContextMenu` のCSS枠線を無効化 (`border:0`)。
- 既存の `FRBContextMenu.paintEvent` がQt標準の文字・アイコン描画後に描く角丸枠線 **1本のみ** を残す。
- 既存の `NoDropShadowWindowHint` は維持する。メニューの色・項目・横幅・位置は変更しない。

## 検証
- 関連テスト 64 PASS
- 広めのテスト 117 PASS / 17 FAIL / 3 SKIP。17件の失敗は適用前の同じ基準ZIPでも全て再現し、今回増加なし。
- Python構文チェック PASS
- `scripts/check_context_menu_contract.py` PASS

## 実機確認
1. `/` から開いた検索欄で「にほん」と入力し、変換・確定できるか。短い／長いフォルダー一覧の両方。
2. 変換確定中のEnterでフォルダーが勝手に着地しないか。
3. `/` で表示した通常操作メニューの四辺が二重線になっていないか。
4. Exp欄から直接右クリックした操作メニューも一重枠か。
