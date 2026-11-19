# FRB Launch 差分 — Sakura URL自動切替 / VS Code固定プロファイル

## 基準 / 適用

- **基準**：`launch_app_20261119_190113.zip`（ユーザー提供最新版）。
- FRB Launchを終了し、念のため既存のソース・設定をバックアップする。
- 差分ZIPをFRB Launchの**ルート**へ展開し、同名ファイルを上書きする。
- `_run_windows_Try_Sakura_Overlay.bat` で3つのOverlayを有効にして検証する。
- VS Codeのみの検証には同梱の `_run_windows_Try_VSCode_Overlay.bat` も使用可能。
- `state.ini`・ビルドBAT・正式リリース設定は**変更していません**。試験用環境変数が引き続き必要です。

## Sakura → Browser → Sakura

1. 第3列のサクラで複数のTXTファイルを開く（未保存テキストを含んでもよい）。
2. URLをダブルクリックする。サクラの実ウィンドウを**閉じずにデスクトップへ外出し**し、Launchの第3列にBrowserでURLを表示する。
3. もう一度TXTをダブルクリックする。Launchが把握しているサクラの**同じHWND**を再収容し、保存していない編集内容・タブを引き継ぐ。
4. 自動外出しが安全に確認できない場合は切替を止め、URLをChromeへフォールバックしない。下部に通知する。

**注意**：ウィンドウの識別はLaunchが以前確認したものに限ります。外出し後にサクラの該当ウィンドウを閉じたり、別のファイルへ切り替えてタイトルが変わった場合、安全確認に失敗する場合があります。その場合は誤収容せず、通常の新規ファイルオープンを試みます。

## VS Code固定プロファイル

旧：`%LOCALAPPDATA%\FRBLaunch\VSCodeGuest\launch-<毎回変わるUUID>`

新：`%LOCALAPPDATA%\FRBLaunch\VSCodeGuest\profile-v1`

- サインイン、テーマ、設定などはVS Codeが上記ディレクトリへ保存し、**Launchを再起動しても引き継がれます**。
- 初回は新しい固定プロファイルなので、**一度だけGitHub/Microsoftへログインし、テーマを設定**してください。2回目以降に維持されるか検証します。
- 通常のデスクトップ版VS Codeのプロファイルとは**共有しません**（誤ウィンドウ取り込み防止）。
- 以前の `launch-UUID` フォルダーは削除・自動移行していません。**ログイン情報を強制コピーする処理はありません**。
- 過去に外出ししたVS Codeウィンドウが残る状態での別ウィンドウ起動／OAuthコールバックは、実機で追加確認が必要です。
- プロファイルを初期化したい場合は、VS Codeを全終了してから `profile-v1` を別名退避してください。Launchからは自動削除しません。

## テスト

Python構文検証と、Sakuraの安全な外出し・再収容、URLハンドリング、VS Codeのプロフィール・HWND識別のテストを実施しています。実機の描画、IME、GitHub OAuthリダイレクト、タブ操作はこの環境では確認できません。

推奨するWindowsでの操作回帰シナリオ：

- `001.txt → 002.txt → 003.txt → 001.txt → 002.txt`（前回の成功確認を維持）
- 未保存テキストありの `002.txt → URL → 002.txt`（内容とタブが維持されるか）
- `002.txt → URL → 001.txt → URL` の繰り返し（Chrome誤起動・無限ダイアログがないか）
- サクラのタブ切替が未完了の瞬間にURLを開く（安全な拒否・編集継続）
- VS CodeでGitHub/Microsoftにサインイン、テーマ変更 → Launch終了 → 起動し直してJSONを開く（サインインとテーマが保持されるか）

## 差分構成

- `src/expanded_view.py` — URL切替の自動外出し／失敗時フォールバック抑止
- `src/studio_preview_panel.py` — サクラの追跡情報保持／安全な再収容
- `src/vscode_guest_bridge.py` — Launch専用固定VS Codeユーザーデータ
- `_run_windows_Try_VSCode_Overlay.bat` — VS Code単独試験用BAT
- `tests/test_*.py` — 新規・改定回帰テスト

本番ビルド・INI統合はまだ未実施です。
