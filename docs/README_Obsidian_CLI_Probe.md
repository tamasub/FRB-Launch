# FRB Launch / Obsidian CLI 90文字応答診断 — 2026-11-18

## 分かったこと

- `obsidian_dock_trace.jsonl` の `main_verify` は返却コード0、標準出力1行90文字だが、`FRB_MAIN_TITLE:` を含まない。
- DOSログではObsidianが `eval` コマンドを**受信**している。ただし、JavaScript評価の成否／実際の標準出力はDOSログにはない。
- この時点でWin32 HWND照合やSetParentまでは処理が進んでいない。

## 使い方

1. **前回適用済みのFRB Launch本体**へこのZIPをそのまま上書き展開。Launchのソースファイルは一切変更されません。
2. Obsidian本体を起動してVaultを開いた状態にする。
3. `tools\Obsidian_CLI_Probe.bat` をダブルクリックする。
4. `reports\Obsidian_CLI_Probe_LOCAL_REVIEW.txt` を開き、タイトル・パス等の機微情報を確認・必要に応じて伏せてから送る。

**安全性**: ノート本文取得、ノートオープン、ファイル編集、CLI設定変更、Window HWNDへの操作、SetParent、外部送信はしない。固定文字列のJavaScript評価 (`'FRB_CLI_DIAG_20261118_OK'`) とバージョン確認だけを実行する。標準出力・標準エラーだけローカルに保存する。Launchアプリは無変更。`eval` が実行拒否されているかどうかは結果を見ないと分からない。

`eval-constant` が固定文字列を返す場合は、次に特定Vaultの指定と`main_verify`コード／Win32照合の問題を調べる。固定文字列が返らない場合は、CLI設定・権限・出力フォーマット・初期化などの問題を先に切り分ける。

**重要**: 元のDOSログの `sqlite... Invalid total_dict_size`、CSP report-only警告は見えるが、これらがCLIの90文字問題を引き起こした証拠はない。
