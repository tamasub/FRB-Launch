# FRB Launch — 第3列の隠しオプションを state.ini に統合

対象: `launch_app_20261117_152529(1).zip` に、直前の `FRBLaunch_HiddenEditorHosts_MD_Obsidian_PreviewWidth_20261117_diff.zip` を適用済みのソース。

## 設計・責務

- 設定値: `%LOCALAPPDATA%\FRBLaunch\state.ini` の `[General]`
- 配布時の初期値: `FRB_Launch\defaults\state.ini`（初回起動のみ取り込み。既存ユーザー設定は上書きしない）
- 表示/非表示: オプション設定画面の ViewDef（**今回は追加・変更しない**。将来の画面公開時に対応）
- Browser Preview は本設定に関係なく従来どおり。

今回の3キー:

```ini
[General]
embed_studio=false
embed_obsidian=false
embed_sakura=false
```

すべて初期値は `false` です。既存のユーザー `state.ini` にこれらのキーが無い場合も `false` として動作します。`true` にすると、それぞれ第3列収容の試験機能を有効にします。変更後はLaunchを再起動してください。

## 変更ソース

- `src/third_column_host_options.py`: `UserConfig/third_column_hosts.json` の読み込みを廃止し、ユーザー `state.ini` を参照。
- `src/launch_state_defaults.py`: 新しい3キーを初回配布値の許可リストに追加。
- `defaults/state.ini`: 初回配布時の値を3件ともOFFで追加。
- `tests/test_hidden_editor_routes_and_preview_width_20261117.py`: 判定のテストをINI方式に更新。
- `tests/test_launch_state_defaults_20261115.py`: 初回シードのテストを追加。

`third_column_hosts.json` は以後参照しません。残っていても動作に影響しません（不要なら手動削除可能）。**自動削除はしません。**

## 適用方法

1. Launchを終了し、適用対象フォルダーをバックアップ。
2. 本ZIPを **Launchプロジェクト直下** に展開して、同名の変更ファイルだけ上書き。`src` フォルダー丸ごとの置換・削除は禁止。誤って `docs/src` に配置しないこと。
3. **注意: `defaults/state.ini` を独自に編集している場合は、ZIPの同名ファイルで丸ごと上書きせず、上記3キーを `[General]` に手動で追加する。** 同梱の `defaults/state.ini` は基準版の例として扱う。
4. 既存ユーザーの `%LOCALAPPDATA%\FRBLaunch\state.ini` は**変更しません**。試験機能を使う場合のみ、既存ファイルの `[General]` に目的のキーを `true` で追加する。
5. Launchを再起動。

## 今回変更しないもの

- オプション設定画面 / ViewDef
- Obsidian・サクラエディタの第3列内での入力問題（引き続き実験機能のため初期OFF）
- Launch専用Studioのプロセス再利用（別案件）
- 既存のJSON / Markdownの開く動作、Browser Preview、列幅の保存・復元

## テスト

- 変更対象のテスト: 16件PASS
- 広めの関連テスト: 60件PASS / 3件FAIL（3件は元版から存在するレガシー期待値の不一致：`editor_window_title`不在2件、旧Stubの`open_bookmark_web_view`不在1件）
- Windows実機での動作検証は未実施。
