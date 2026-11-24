# FRB Commander — 旧Launch設定JSONのExpanded移行

目的：旧設定を最新の Files / Browser (Expanded) の起動条件に合わせる。会社の実JSONは未提供なので、最新版の `expanded_view_model.py` / `app.py` と同梱テンプレートを根拠に対象を限定した。

## 使い方

1. `Migrate-LaunchConfig.ps1` を FRB Launch の Files List で右クリックし、FRB Commander を起動する。
2. 「診断・変更予定のみ」または「移行JSONを別名保存」を選択するだけ。Ctrl+Enter → 実行確認。入力は実行ユーザーの `%LOCALAPPDATA%\FRBLaunch\UserData\frb_launch_data.json` を自動参照。存在しない場合はエラー終了し、配布テンプレート等へフォールバックしない。PowerShellから直接実行する場合だけ `-InputJson` で別ファイルを指定できる。
3. 出力ログを確認する。変換時は原本と同じフォルダーに `<旧名>_migrated_<ID>.json` を新規保存する。原本は一切変更しない。
4. 反映するPCでLaunchとStudioを完全終了する。既存の `%LOCALAPPDATA%\FRBLaunch\UserData\frb_launch_data.json` があればバックアップし、変換後JSONのコピーをこの名前で配置する。旧 `config` フォルダーよりUserDataが優先される。
5. `%LOCALAPPDATA%\FRBLaunch\state.ini` の `[General]` に `view_mode=expanded` を設定する（既存の同名キーは置換、他の設定はそのまま）。またはLaunch画面の Three-layer ボタンで切り替える。起動後にFiles/Browserを確認する。state.iniがなければ現行アプリの既定値がexpanded。

## 移行内容

- `config/expanded_view_options.json` のIDを使用（なければ標準：`system` / `folders` / `__browser_bookmarks_root`）。
- 対象Pageと専用2ルートが存在しない場合は追加。Pageとブックマークルートは有効化する。既存Filesルートのenabledは変更しない（Expandedはこのフラグを無視する）。
- 専用ルートは対象Page直下へ移動。配下の子孫のpage_idも同期し、親子関係を維持。既存のタイトル、会社独自の項目、アクション、変数、選択肢、パス、その他のフィールドは原則保持する。サンプル登録をコピーしない。
- ブックマークの専用sourceと初期化済みフラグを設定する。
- 未知の別IDブックマークルート、専用IDの用途衝突、不正な階層、未対応アクション等はエラー終了。汎用スキーマ移行、会社固有パス修正、state.ini自動更新はしない。
- JSONはUTF-8（BOMありも可）。出力はUTF-8、整形されるためバイト一致ではない。入力は不変。数値精度を維持できない整数等は拒否する。その他のJSONの特殊な数値表現、重複キー、現在の全入力検証に対する網羅保証はしない。

## 実行環境

PowerShell 5.1 + 同梱Node.js。Portableでは `runtime/node/node.exe` → `Studio/runtime/node/node.exe` の順で探索し、PATHは使用しない。開発環境のみ隣接Studio/PATHも探索する。Launch本体の変更、ビルド不要。

## 検証

- Nodeテスト6件：旧Pageからの移動、専用ルート追加、無効Page、衝突拒否、設定ID、原本非変更／別名保存。
- 最新同梱テンプレートを旧構造にしたテストデータで、現行Python `core.validate` / `expanded_targets` / `should_expand` の通過、および両モードのCommander argv構築を確認。
- AppData自動参照版：現行CommanderのViewDef検証と引数生成、Nodeテストを再確認。
- Windows PowerShell・Commander GUI・会社の実JSONは未検証。現行アプリのすべての検証条件をJSで再実装したわけではない。まず診断を使用すること。
