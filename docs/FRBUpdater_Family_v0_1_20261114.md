# FRB Updater Family v0.1 — 導入・配布・テスト手順

2026-11-14 / 対象: `FRB_Launch` + 同梱 `FRB_Studio`

## 目的・責務

- **FRB Launch**: バージョンアップ情報UI。ユーザーが「最新版を確認」→「更新を開始」を操作して初めて更新する。
- **Updater更新用ヘルパー（共通）**: `src/frb_update/bootstrap.py`。別アプリからも呼べる、アプリ非依存のPython標準ライブラリ部品。Updater用Feed取得、Updater EXEダウンロード／SHA-256照合、バージョン別配置、Updater起動。Python以外のアプリ向けに、同じ実装を呼び出すCLI入口 `src/frb_updater_helper_main.py` と `_build_updater_helper_windows.bat` も用意。**更新ロジックは一本だけ**。
- **FRB Updater本体（独立EXE）**: `src/frb_updater_main.py` + `src/frb_update/updater_core.py`。LaunchとStudioの完全ZIPを検証して適用し、異常時は旧Systemファイルを復元。Updaterの自己更新はしない。
- **配布作成**: `scripts/build_release_package.py` と `scripts/build_updater_feed.py`。GitHub Releases等の配布サイトへの公開処理は実装しない。配布URLはSystem設定で明示指定する。

## SystemとUserの境界

| 項目 | 扱い |
| --- | --- |
| `FRBLaunch.exe` および `_internal` 等 | System更新対象 |
| `Studio/NativeShell/_publish`、`Studio/wwwroot`、`Studio/defs`、`Studio/tools`、`Studio/runtime` | System更新対象 |
| `Studio/data/json/00_rules` | System側の規則定義として更新可 |
| `Studio/data/json/01_main`、`Studio/data/markdown` など研究・利用者データ | **更新禁止** |
| `%LOCALAPPDATA%/FRBLaunch/UserData/` | **更新禁止** |
| `%LOCALAPPDATA%/FRBLaunch/UserConfig/` | **更新禁止** |
| `%LOCALAPPDATA%/FRBLaunch/state.ini`、WebViewプロファイル | **更新禁止** |
| `config/frb_launch_data.json`（旧配置） | **更新禁止**。初回ユーザー移行以外で触らない |
| `defaults/frb_launch_data.template.json` | System。明示的な「初期化」にのみ利用 |
| `updater/versions/<version>/FRBUpdater.exe` | 共通ヘルパーのみ更新。統合ZIPには収録しない |

現行の `git_commit_options.json` はマシン固有のリポジトリパスを含むため、**最初の起動時だけ** `config/` から `%LOCALAPPDATA%/FRBLaunch/UserConfig/` へコピーする。以後はユーザー設定を優先し、System版から再コピーしない。既存の `backup_frb_launch_config_log.bat` は既に `UserConfig/*.json` をバックアップする。

**重要**: Updaterは任意フォルダーを削除しない。新しいZIPに含まれるSystem管理ファイル、および前回の `installed_release.json` で管理対象だった旧Systemファイルに限り置換／整理する。初回の未管理旧ファイルを一括削除する機能はない。

## 配置

完成したインストール用フォルダーの概念例:

```text
FRBLaunch/
  FRBLaunch.exe
  _internal/
  config/                       ← System側デフォルト設定（旧ユーザーデータは含めない）
  defaults/
  defs/launch/...
  updater/versions/0.1.0/FRBUpdater.exe
  Studio/
    NativeShell/_publish/FRBStudio.NativeShell.exe
    wwwroot/
    defs/
    tools/option_settings/cli.mjs
    tools/change_core/cli.mjs
    runtime/node/node.exe
  installed_release.json         ← Updaterによる更新成功後の管理情報
```

`Updater` 実行中のEXEと更新対象のLaunchファイルを衝突させないため、Updaterは `updater/versions/<version>/` に独立して置く。Updater自体の新バージョンはLaunchが起動前にダウンロード／準備する。従来の「もう一人の更新ヘルパーEXE」を作らない。

## 1. Windows上でビルド

1. Launchで `_build_windows.bat` を実行し、`dist\FRBLaunch\FRBLaunch.exe` を作る。
2. Studioで `cmd_compile_NativeShell.bat` を実行し、`NativeShell\_publish\FRBStudio.NativeShell.exe` を作る。
3. Windows版Node.js公式配布物の `node.exe` を、Studio側の `runtime\node\node.exe` （または Launchのビルド済みフォルダーの `runtime\node\node.exe`）に配置する。Node.exeはソースZIPには含まれていない。利用許諾も配布物に添付すること。
4. Launchで `_build_updater_windows.bat` を実行する。`dist\updater\FRBUpdater.exe` が生成される。PythonやPyInstallerが利用者PCに存在する必要はない。必要なら `_build_updater_helper_windows.bat` で別アプリ用CLI EXEも作成できる。
5. 必ず**完成済みのビルド成果物**から配布完全ZIPを生成する（ソースの `launch_app_*.zip`、`FRBStudio_App*.zip` を更新配布しない）。

Studioのランタイムは、コンパイル後のStudioリポジトリを入力フォルダーとして指定可能。ただし配布ビルダーが許可されたSystem領域のみ抽出し、`Studio/data/json/01_main` 等は自動的に除外する。

## 2. Launch＋Studio 統合完全ZIPを作る

`FRB_Launch` ルートのPowerShellで（バージョンは**例**。正式値はリリース決裁時に指定）:

```powershell
.\.venv\Scripts\python.exe scripts\build_release_package.py `
  --launch-dist "F:\FRB_Apps\FRB_Launch\dist\FRBLaunch" `
  --studio-runtime "F:\FRB_Apps\FRB_Studio" `
  --launch-source "F:\FRB_Apps\FRB_Launch" `
  --output "D:\Release\FRBLaunch_1.0.0.zip" `
  --version 1.0.0 --launch-version 0.9.0 --studio-version 0.18.0 `
  --notes "統合版リリース" `
  --archive-url "https://<正式な配布先>/FRBLaunch_1.0.0.zip"
```

この例のURLおよびStudioバージョンは仮値。`--archive-url` を省略するとZIPだけ生成され、`product_feed.json` は生成されない。公開用URLを与えた場合、ZIPと同じ場所に `product_feed.json` が生成される。**実際に配布するZIPとFeedに指定されたZIPは、SHA-256とバイト数が一致する必要がある**。

`defaults/frb_launch_data.template.json` はユーザー指定の現行テンプレートをそのまま配布する。現在のテンプレートには個人のメニュー・パス等が含まれる可能性があるため、**第三者に公開する前に人間が内容を承認すること**。

## 3. Updater EXEの配布情報を作る

```powershell
.\.venv\Scripts\python.exe scripts\build_updater_feed.py `
  --exe ".\dist\updater\FRBUpdater.exe" `
  --version 0.1.0 `
  --url "https://<正式な配布先>/FRBUpdater.exe" `
  --output "D:\Release\updater_feed.json"
```

**実在しないURLは設定しない。** 2つのJSON（`updater_feed.json` / `product_feed.json`）と本体をHTTPSで取得できる場所に公開する。非公開GitHub Releasesを匿名ダウンロードすることはできないため、別途認証付き配信の設計が必要。現段階では公開先を決めていない。

公開後、Launch System領域の `defs/update/update_sources.json` を実在するHTTPS Feed URLへ更新する:

```json
{
  "schema": "frb-update-sources-v1",
  "updater_feed_url": "https://<正式な配布先>/updater_feed.json",
  "product_feed_url": "https://<正式な配布先>/product_feed.json",
  "allow_local_for_test": false
}
```

未設定（空文字）の場合はUIに「配布先未設定」と表示され、更新実行できない。Updaterのアップデートは **Launch側の共通ヘルパー** が実施する。

## 4. 起動方法

Launchの設定メニューで **「バージョンアップ情報...」** を選択。現在の統合版とLaunch/Studioバージョンを表示する。`最新版を確認` は2つのFeedを非同期確認する。新しい統合版があり、正式にビルドされた単独配布の `FRBLaunch.exe` から起動している場合だけ `更新を開始` が有効。

`更新を開始` を明示的に選ぶと、共通ヘルパーが最新Updaterをダウンロード・ハッシュ照合し、アップデート要求を渡してUpdaterを起動。Launchは通常の終了処理を通る。UpdaterはLaunch/Studioの終了を待ち、完全ZIPを検証しSystem領域をバックアップ→適用する。成功時はLaunchを再起動。失敗時には旧ファイルを復元し、旧Launchの再起動を試みる。

更新ログ・結果は `%LOCALAPPDATA%\FRBLaunch\UpdateLogs\`、Systemバックアップはインストールフォルダーの隣に作られる `.<フォルダー名>_update_backups/` に保存。

**開発時の `dist/FRBLaunch/launch_home.json` がある構成からの実行は更新禁止。** 完成した統合版フォルダーでのみ更新が許可される。作業中のソースリポジトリを誤って上書きすることを防ぐ。

## 5. ローカル試験と未完了事項

ローカルの `file://` による試験は `update_sources.json` の `allow_local_for_test: true` を明示したときだけ可能。Updater CLIでも `--allow-local-for-test` を別途付与した場合に限る。公開構成では必ずfalseに戻す。

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_frb_updater_family_20261114.py
.\.venv\Scripts\python.exe scripts/check_dialog_contract.py
.\.venv\Scripts\python.exe scripts/check_context_menu_contract.py
```

**未完了:** Windows 11でのUI・ビルド済みUpdater EXE・実際のHTTPS配布／正常更新／Studio起動の通しテスト。現在の環境はWindows/.NET/PySide6実機ではないため、ソース単体のテストとZIP適用の検証まで。

**リリースv0.1の技術制約:** HTTPS + SHA-256で整合性を確認するが、Feedの電子署名までは持たない。配布元の管理権限・TLS・公開手順を保護すること。複数アプリが同一インストール場所を共有する構成は対象外。

## 共通ヘルパーを他アプリから呼ぶ例

FRB Launch自身は同一の `frb_update.bootstrap` ライブラリを直接呼ぶ。将来、C#・Node.jsなどPython以外のアプリは、次の独立CLIを利用できる:

```powershell
.\dist\updater_helper\FRBUpdaterBootstrap.exe `
  --updater-feed "https://<正式な配布先>/updater_feed.json" `
  --product-feed "https://<正式な配布先>/product_feed.json" `
  --install-root "C:\Apps\FRBLaunch" `
  --work-dir "$env:LOCALAPPDATA\FRBLaunch\UpdateWork" `
  --host-pid 12345 --host-exe FRBLaunch.exe
```

正常時はJSON形式で `{"started":true,...}` を返す。呼び出し元は成功を確認して**自身を正常終了**する。ヘルパーの内部にFRB Launch固有のQt/UI/設定JSON処理はない。例のパス・PID・URLは実行時に渡す情報であり、実在する配布先を自動発見する機能ではない。
