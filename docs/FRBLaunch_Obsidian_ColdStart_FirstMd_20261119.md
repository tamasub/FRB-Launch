# FRB Launch – Obsidian初回起動時のCLI準備待ち・初回Markdown確定 (2026-11-19)

## 適用元

- `launch_app_20261119_122553.zip`（2026/11/19 12:25:53版）
- **差分ZIP**：Launchルートに展開・上書き。Studioの再ビルド不要。
- 変更：`src/obsidian_dock_bridge.py`、`src/studio_preview_panel.py`、専用テスト1本とこの記録のみ。

## 実機から判明した症状

- Obsidianを起動中に `obsidian eval ...` を呼ぶと、終了コード0なのに `Error: Command "eval" not found` が返る場合がある。
- 本体起動後、PowerShellから `obsidian eval 'code=1+1'` を実行すると `=> 2` を確認済み。
- 完全停止状態から最初の `.md` をダブルクリックすると、Obsidian本体だけ起動し、その `.md` が表示されない場合がある。

## 改修した状態遷移

1. 最初のダブルクリック → 既存のVault本体起動URI **1回**（ポップアウト生成禁止）。
2. バックグラウンドでCLI準備の読み取り専用確認。`eval` コマンド利用可能・本体root leafあり・**選択したMarkdownがVault APIで見える**まで待つ。
3. 初回の対象Markdownを**本体の既存leafへ** `openFile` する。URIに `.md` を先送りしない。
4. 別CLI呼び出しで、**本体leafがそのMarkdownを表示していること**を確かめる（stdout／終了コードだけで成功扱いしない）。
5. 検証できた本体ウィンドウのタイトルと、Win32 HWND候補との一致を確認して第3列に収容。
6. 初回の開く命令で確かな応答が返らなくても、先に実際の表示状態を検証。必要なら準備完了を再確認してリトライ。正常応答後に表示が確認できない場合は、**同一ファイルへのopenFile再試行を最大1回まで**行う。別ウィンドウは生成しない。
7. 準備・収容できなければ約30秒でタイムアウト。Obsidian本体を終了・強制収容しない。

追加のHUD/常駐監視/外部プロセス操作はなし。Browser、Studio、サクラ、およびExp Keyborderには触れていない。

## 検証

- CLI終了コード0でも `eval not found` が返れば未準備扱い。
- 未準備4回→準備成功→初回Markdownオープン→表示検証→収容。
- Vaultの索引にファイルがまだ現れない場合は `openFile` を発行しない。
- CLI応答が曖昧でもファイル表示を優先して確認。
- 表示が遅れた場合、同一Markdownだけ最大1回再要求。
- 起動タイムアウトでも余計なウィンドウを生成しない。
- 専用＋関連テスト **84件PASS**。広めのテスト **177件PASS・11件FAIL**。同じ旧テストの失敗11件は改修前の元ZIPでも再現（改修前168件PASS・11件FAIL）。
- Windows 11実機のObsidian操作は未検証。テストPASSと実機成功は別。

## 実機確認手順

1. Obsidianを通常終了してから、Launchで `A.md` をダブルクリック。**A.mdが第3列のObsidian本体に表示されるか**確認。
2. `B.md` をダブルクリック。Bへ切替、ポップアウト窓が新規生成されないこと。
3. Obsidianを起動したままLaunchで `A.md` を開く。初回・既存の両経路を比較。
4. 失敗時は、`%LOCALAPPDATA%\FRBLaunch\obsidian_dock_trace.jsonl` を確認。`CLI_RESULT` の `startup_ready` / `main_open` / `main_verify`、`HWND_SELECTION` / `SETPARENT_*` のステージで停止位置を特定。ログはファイル名やVault名を記録しないよう配慮しているが、共有前に内容確認推奨。

## 注意

**Obsidian本体の収容が成功したという報告ではない。** `eval` の起動時エラーへの対応と、初回ノート表示の合否を明示する改修であり、Win32タイトル一致や`SetParent` の相性問題が別途残る可能性あり。
