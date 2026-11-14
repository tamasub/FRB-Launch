# FRB Launch 0284 — FRB_Apps 移転パスの安全移行

対象：`F:\FRB_Apps\FRB_Launch` にコピー移転済みで、兄弟フォルダー `F:\FRB_Apps\FRB_Studio` が存在する環境。

## 適用手順（Launch再ビルド不要）

1. **Launchをタスクトレイから完全終了**する（`FRBLaunch.exe` が残っていないこと）。Studioも設定を編集していれば閉じる。
2. 差分ZIPを **`F:\FRB_Apps\FRB_Launch`** に展開（フォルダー階層を保持）。**旧 `F:\FRB\tools` 側には展開しない**。
3. `_migrate_frb_apps_paths_0284.bat` をダブルクリック。
4. 対象ごとの変更前・変更後が表示されるので確認し、`Y` を押して適用。取りやめる場合は `N`。
5. 完了後Launchを起動し、My WorkのZIP保存・登録済みLaunchフォルダー・Studioのデータフォルダー表示などを確認。

実行ファイル／アプリ本体のソースは変更しない。**Launchの `_build_windows.bat` 再実行は不要**。

## 移行するデータ

- `config/frb_launch_data.json` の実行ターゲット・登録フォルダーの**旧アプリ配置だけ**
  - `F:\FRB\tools\FRB_Launch\...` → `%launch_home%\...` （実行時に現在のLaunch配置へ展開）
  - `F:\FRB\tools\FRBStudio_App\...` → `%studio_root%\...` （実行時に検出した兄弟Studioへ展開）
  - 上記と**完全一致する操作対象の実パス説明** → 新配置の実パス
  - `launch_variables` の旧 `studio_root` リテラル → 現在の兄弟Studioの実パス（フォールバック用）
- `config/file_index_options.json` の旧Launch索引ルート → 現在のLaunch実パス
  - 索引の `index_folders` はWindowsの絶対パスが必要。`%launch_home%` は使わない。

既存凍結版のプレビュー想定：`frb_launch_data.json` **23フィールド**、`file_index_options.json` **1フィールド**。
実機の編集内容によって変更件数が異なっても問題ないが、差分を確認すること。

**変更しないもの**：PageやItemのID・タイトル・並び順、追加したユーザー項目、自由記述のメモ、FRB研究データ `F:\FRB\data`、資料 `F:\FRB_docsExcel`、旧パスを歴史として記録した文書・テストフィクスチャ。

## バックアップ・変更差分

適用直前に下記へ変更前の両ファイルを退避し、フィールド差分の unified diff を生成。

```
F:\FRB_Apps\FRB_Launch\backups\frb_apps_paths_0284_YYYYMMDD_HHMMSS_xxxxxx\
    frb_launch_data.json
    file_index_options.json
    migration_diff.patch
```

- プレビューだけでは元JSONもバックアップも書き換えない。
- 2回目の実行は変更なし（冪等）。
- 破損JSON、起動中のLaunch、想定外の配置、実行中に変更された設定を検出した場合は更新を止める。
- 更新中の異常時には書き換え済みのファイルをバックアップからロールバックする。

## コマンドによる実行（任意）

```powershell
cd F:\FRB_Apps\FRB_Launch
.\.venv\Scripts\python.exe scripts\migrate_frb_apps_paths_0284.py
.\.venv\Scripts\python.exe scripts\migrate_frb_apps_paths_0284.py --apply
```

## Windows実機での確認ポイント

- `FRB Launch をZIP保存`、`_make_launch_zip.bat`、`_build_windows.bat` が新Launchのファイルを開く。
- Files Expの `FRB_Launch` は新Launchルートを表示する。
- 既存名 `FRBStudio_App\data\json` の登録フォルダーが**新Studio**の `data\json` を開く（表示名はユーザー設定のまま残す）。
- Launch →「メニュー設定 (FRB Studio)」が引き続き動く。
- `F:\FRB` 研究用パスと `F:\FRB_docsExcel` は変更されていない。
- Windowsスタートアップの既存ショートカットが旧フォルダーを向いている場合は**別途** `setup_startup.bat` 等で再登録する。移行ツールはショートカットを変更しない。

## 検証状況（提供時）

- 新規移行テスト・関連既存テスト：**40件PASS（サブテスト7件含む）**。
- 凍結版の実JSONコピー：移行前後の差分を検証。原本は未変更。
- 一括回帰の旧テスト `test_remote_files_exp_registered_roots_20261101.py` には、現在のExp D&D実装に対して過去の `DragDropMode.DropOnly` 文字列を要求する既存テスト不整合が1件ある。本移行スクリプトとは無関係。
- Windows実機でのJSON編集後Launch動作・コマンド実行は未確認。
