# FRB Launch: Exp登録パス／Studio詳細設定／更新画面／Feed永続化

対象: 2026-11-14、統合版0.9.3・Launch0.9.1・Updater0.9.3のテスト環境。

## 現象と原因

1. Exp登録の「FRB_Launch」は `%launch_home%`、Studioは `%studio_root%` を参照していた。`F:\FRB_Update_Test\FRBLaunch` から起動すると、**実行中の環境のパス**に展開される。JSONの登録文字列が書き換わったとは限らない。
2. 「メニューITEMの詳細設定」で呼び出すStudioも、実行中のLaunchに同梱されたStudioを優先していた。開発用 `F:\FRB_Apps\FRB_Studio` とテスト用のStudioが混同される。これがエラーの一因である可能性は高いが、エラー全文が未取得のため他原因は未確定。
3. 進捗の完了時にマーキースタイルが残る問題、Feed URLがSystem更新で消える問題も別途残存。

## ソース修正

- `launch_source_root = F:\FRB_Apps\FRB_Launch` と `studio_source_root = F:\FRB_Apps\FRB_Studio` を、更新テスト用のインストール先と独立した **Launch Data の変数**として追加。
- Exp内の `FRB_Launch`、`FRB Studio`、`FRBStudio_App\\data\\json` の登録先を上記変数へ切替。変数参照のOpen操作も同期。登録されている他の項目は変更しない。
- Launchの「Studioで詳細設定」を開く経路では、**有効な開発用Studio実行ファイルが存在するならそちらを優先**。ない場合は従来の同梱Studioへフォールバック。Studioで編集するLaunch Dataは従来どおり UserData の正本を使用する。
- UpdaterのWin32進捗UIはマーキーと数値バーを分離。完了は必ず数値100%、失敗は0%。
- `UserConfig/update_sources.json` をFeedの優先保存先として採用。古いSystem値が有効なら一度だけ移行。Updater管理対象から既に除外された領域を使用。
- Launchのソースバージョン `0.9.2`（統合版としての想定次バージョン `0.9.4`、Updaterソース次版 `0.9.4`）。**今回のZIPはソース差分であり、配布用EXEやFeedを更新しない。**

## 今すぐできる安全な修復（更新操作なし）

LaunchとStudioを完全終了（タスクトレイ含む）。差分ZIPを `F:\FRB_Apps\FRB_Launch` に展開。PowerShell 5.1から以下を実行。

```powershell
cd F:\FRB_Apps\FRB_Launch
powershell -NoProfile -ExecutionPolicy Bypass -File .\repair_FRBLaunch_exp_roots.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File .\repair_FRBLaunch_exp_roots.ps1
```

修復対象は `%LOCALAPPDATA%\FRBLaunch\UserData\frb_launch_data.json` のうち既知のExp登録行と関連Studio起動アクション、追加変数のみ。意味上それ以外の項目は変えない。上書き前に `%LOCALAPPDATA%\FRBLaunch\UserData\_Backups\` に元JSONを丸ごと保存する。既存の独自登録は維持。UTF-8日本語を保持するが、JSONのインデントが揃うためテキスト上は広く差分が出る可能性がある。

URL未設定を修復する場合、**ローカルテストフォルダーだけ**を対象とする別コマンドを実行。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\repair_FRBLaunch_test_feed.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File .\repair_FRBLaunch_test_feed.ps1
```

配布フォルダーの `updater_feed.json` と `product_feed.json` の存在とschemaを確認し、`F:\FRB_Update_Test\FRBLaunch\defs\update\update_sources.json` と `F:\FRB_Update_Test\FRBLaunch\UserConfig\update_sources.json` を設定する。既存System JSONは `.bak` に退避。**既存の有効な別UserConfigのURLは勝手に上書きしない**。Journalや更新バックアップには一切触れず、更新実行もしない。

## Launchの詳細設定エラー修正を反映するには

上記のAppData修復だけでExpパスは直る。しかし **Launch.exe内のStudio選択処理**はビルド済み実行ファイルを変えない限り古いままなので、次が必要。

1. `F:\FRB_Apps\FRB_Studio\NativeShell\_publish\FRBStudio.NativeShell.exe` が存在することを確認。なければStudio側をビルドする。
2. `F:\FRB_Apps\FRB_Launch\_build_windows.bat` でLaunchを再ビルド。
3. まず開発用の `F:\FRB_Apps\FRB_Launch\dist\FRBLaunch\FRBLaunch.exe` から設定編集が開くことを試す。実行中の既存Launchは必ず終了させる。
4. 更新テスト先へ入れるなら新しい統合版 0.9.4 とUpdater 0.9.4の別配布パッケージを作成する。**0.9.3の配布ZIPやUpdater EXEを上書きしない**。5,111ファイルの完全ZIPを再生成・検証し、Feedへ新バージョンを向けてから更新する。

現在のインストール済みLaunch0.9.1には、ソース修正を展開しても自動では反映されない。

## テスト証跡

関連するPythonテストは43件PASS。PySide6がこのLinux環境にないため、Windows GUI総合テストと全pytestスイートは未実施。Studioの元の起動エラー全文は未入手で、実機での根本原因の追加確認が必要。
