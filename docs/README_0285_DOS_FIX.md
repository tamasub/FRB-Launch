# FRB Launch 0285 — 0284移行BATのDOS窓瞬断修正

## 原因調査

0284で配布した `_migrate_frb_apps_paths_0284.bat` は **UTF-8の日本語入りかつLF改行のみ** でした。Windowsの `cmd.exe` で想定外の解析や早期終了が起きる可能性があるため、BATを **ASCII英字のみ・Windows標準CRLF改行** に変更しています。ユーザー環境の実際の終了理由は未確定です。

Pythonの設定移行ロジック `scripts/migrate_frb_apps_paths_0284.py` は変更していません。

## 変更点

- BATをASCII + CRLFで書き直し、文字コードや改行による解釈差を回避。
- プレビューが成功した場合のみ **Y/N確認** を表示。
- `Y` 以外では `--apply` を呼び出さない。
- エラー、キャンセル、成功いずれも最後に `pause` して画面を閉じない。
- 失敗した理由を画面に表示し、プレビュー／適用ログを保存。
- `.venv\Scripts\python.exe`、`py -3`、`python` の順で起動手段を探す。
- Launch設定JSONはZIPに同梱しない（移行前の現物を保護）。

## 適用

1. Launchをタスクトレイから終了。
2. 差分ZIPを `F:\FRB_Apps\FRB_Launch` に、フォルダー階層を保持して上書き展開。
3. `_migrate_frb_apps_paths_0284.bat` をダブルクリック。
4. プレビュー差分を読み、確認が出れば `Y` または `N` を入力。
5. エラー表示なら画面を閉じずにログを確認。

## 診断ログ

- `migration_logs/frb_launch_0284_preview_last.log`
- `migration_logs/frb_launch_0284_apply_last.log`（Yを押して適用へ進んだときのみ）

**プレビュー段階で失敗した場合は設定JSONは変更しません。**

なお、0284を既に適用済みの場合、プレビューには「差分なし」と表示されます。その場合、再適用しても変更はありません。

## 再ビルド

不要。BATの置き換えのみです。
