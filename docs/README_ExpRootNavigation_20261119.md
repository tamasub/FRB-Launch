# FRB Launch: Files Expにフォルダーが勝手に増える問題（2026-11-19）

## 適用元

`launch_app_20261119_222902.zip` に上書き展開する**差分パッケージ**です。FRB Launchを終了してから適用してください。

## 原因

「移動」なのに `go_to_directory(..., direct_anchor=True)` が指定され、`_direct_entry_root` の設定→`ensure_direct_root()` により、Files Expへセッション専用の一時ルートが作られていました。アプリ再起動では消えていたため、JSONへ保存した登録ルートとは異なります。

## 変更

- ぱんくずの直接入力→青矢印（およびEnter）：**Files Listの移動のみ**。Expの新ルート作成は禁止。
- 第3列ヘッダーの📂：**Files Listの移動のみ**。候補選択仕様は維持。
- フォルダーお気に入り：**Files Listの移動のみ**。
- 普通のフォルダー移動／履歴復元時、以前の操作で作られた `direct_root=True` の一時Expルートだけを削除する。ユーザーが登録したJSON由来のルート／PCはそのまま残す。
- `go_to_directory(..., direct_anchor=True)` と `ensure_direct_root()` 自体は内部互換用に残すが、通常のUI操作では使わない。
- 第3列の収容やBrowserの動作には変更なし。

## Windowsでの確認手順

1. Expに存在しないフォルダー（例: `C:\Users\<ユーザー>\Documents\テスト`）をぱんくずへ直接入力→**青矢印**。Files Listだけが移動し、Exp最下部に新ルートが追加されない。
2. 同じ入力で**Enter**。同じ結果。
3. 第3列で複数のファイルを開いて📂→候補を選択。Files Listだけが移動、Expに新しいルートは増えない。
4. フォルダーお気に入りから移動してもExpに新しいルートは増えない。
5. Exp内の既存の登録ルート、PC、上下の操作、Exp Keyboardを確認。
6. 新しいルートが万一残っている場合、別のフォルダーへ通常移動すると一時ルートだけ削除されること。

## 検証

- Python構文チェック PASS。
- 今回の直接対象のheadlessテストと関連テスト 10 PASS（4件は配布ZIPに欠けているローカルconfigを必要とするため除外）。
- Exp/Remote周辺の広めのテスト 107 PASS / 15 FAIL / 4 deselected。15件の失敗は適用元の**同一ソース**でも再現し、古いUI前提などによる既存の失敗。
- PySide6がこの実行環境にはないため、Windows GUIでのクリック最終確認は未実施。
