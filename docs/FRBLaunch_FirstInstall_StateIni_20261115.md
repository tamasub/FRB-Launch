# FRB Launch — 初回起動時の state.ini 初期値

## ファイルの役割

- **初期値テンプレート（System側）**: `FRB_Launch/defaults/state.ini`
- **利用者の実際の設定（User側）**: `%LOCALAPPDATA%/FRBLaunch/state.ini`
- **読み込み実装**: `src/launch_state_defaults.py` → `src/app.py` の `Launcher` 初期化前に一度だけ実行

## 優先順位

1. User側の `state.ini` が**存在する**：内容は変更しない。`defaults/state.ini` を後で変更しても、適用しない。
2. User側の `state.ini` が**存在しない**：`defaults/state.ini` の `[General]` に記述された対象キーだけを書き出す。
3. テンプレートにキーが**存在しない**、値が不正、またはテンプレート自体がない：そのキーは書き出さず、既存のプログラム内の初期値（QSettings の読み込み時の第2引数）を採用する。

テンプレートは利用者データのコピー元であり、既存設定を変更するためのマイグレーションではありません。インストール後にメニューで設定変更した値は、従来どおりUser側へ保存されます。

## 記述例

```ini
[General]
appearance_theme=light
vdi_no_cursor_warp=true
hide_page_buttons=true
experiment_remote_15_column=true
```

`vdi_no_cursor_warp` は**反転キー**です。`true` = 「マウスポインター自動移動 OFF」、`false` = 「ON」。既存のキー名と動作を変更しません。

## 初期値として読み込めるキー

- `appearance_theme`: `light` / `dark`
- `vdi_no_cursor_warp`: `true` / `false`
- `dismiss_on_outside_click`: `true` / `false`
- `folder_open_mode`: `single` / `double`
- `desktop_remote_enabled`: `true` / `false`
- `hide_page_buttons`: `true` / `false`
- `experiment_remote_15_column`: `true` / `false`
- `experiment_mouse_pointer_rod`: `true` / `false`
- `experiment_mouse_pointer_rod_windows`: `true` / `false`
- `experiment_mouse_pointer_rod_smart`: `true` / `false`

- `embed_studio`: FRB Studioの第3列表示（初回標準 `true`）
- `embed_obsidian`: Obsidianの第3列ご招待（初回標準 `true`。非親子化オーバーレイ方式）
- `embed_vscode`: VS Codeの第3列ご招待（初回標準 `true`）
- `embed_sakura`: サクラエディタの第3列ご招待（初回標準 `false`。通常の外部起動は継続）

**既存インストールへの注意**：この変更は既存のユーザー `state.ini` を上書きしません。Obsidian・VS Codeを使う既存ユーザーは、Launchを終了し `%LOCALAPPDATA%\FRBLaunch\state.ini` の `[General]` に `embed_obsidian=true`、`embed_vscode=true` を追加または修正してください。Studioを第3列で使う場合は `embed_studio=true` も明示してください。`embed_sakura=false` のまま維持します。

旧検証用環境変数 `FRB_VSCODE_GUEST_OVERLAY` / `FRB_SAKURA_GUEST_OVERLAY` は、ユーザー設定キーが未定義の環境でのみ互換動作します。`state.ini` の明示設定が優先です。Obsidianの `FRB_OBSIDIAN_IME_OVERLAY` も同様に、`state.ini` の明示設定がない場合だけ診断用として使います。

このほかのキー（ウィンドウ位置・サイズ・履歴・現在選択など）はテンプレートから取り込みません。これは、PC固有の状態を初期値に混ぜないためです。

## 確認手順

1. `defaults/state.ini` を好みの値に編集。
2. **既存の `%LOCALAPPDATA%/FRBLaunch/state.ini` をバックアップ**（テストする場合のみ）。
3. FRB Launchを終了してから、テスト用のUser側 `state.ini` を退避する。
4. Launchを起動。新規のUser側 `state.ini` が作られ、テンプレートの設定が反映されることを確認。
5. メニューで設定変更してLaunchを再起動。変更した設定が保持されることを確認。
6. テンプレートの値を変えても、既存User側 `state.ini` が上書きされないことを確認。必要なら退避した状態を元に戻す。

**一般ユーザーに対して既存のUser側 `state.ini` を削除してはいけません。** テスト時は必ずバックアップを取り、終了後に復元してください。

## 配布とテスト

`scripts/build_release_package.py` は `defaults/` 以下を配布System ZIPへ含める既存実装のため、`defaults/state.ini` も収録されます。ユーザーの `%LOCALAPPDATA%/FRBLaunch/state.ini` は従来どおり配布・更新対象ではありません。

初期化ロジックの自動テスト: `python -m pytest -q tests/test_launch_state_defaults_20261115.py`

Windows 11上でのQt GUI実動作確認は別途必要です。
