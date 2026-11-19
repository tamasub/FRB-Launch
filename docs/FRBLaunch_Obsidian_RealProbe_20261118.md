# FRB Launch / Obsidian本体収容 v1.0.3 — 実測診断（2026-11-18）

## 基準と変更範囲

- ベース: ユーザー提供 `launch_app_20261118_211000.zip`。
- 目標: ObsidianのVault本体ウィンドウを第3列に収容し、同じ編集領域でノートを切り替える。
- 今回は **実測診断とCLIハンドシェイク分離**。本体HWNDの選定契約、SetParent、既存のStudio/サクラ動作は変更しない。
- ポップアウト新規生成、勝手なプロセス終了、曖昧なHWNDの奪取は行わない。

## 取得できた実測（ZIP内の21:07 Snapshot）

- Obsidian 1.15.1、表示されている本体候補: PID `14740`、HWND `0x5510A0A`、Class `Chrome_WidgetWin_1`。
- Obsidian候補は `ParentHWND=0x0`、`OwnerHWND=0x0`、Visible=True。
- Launch: PID `20204`、HWND `0x73E08AA`。
- **本体ウィンドウがあることは分かったが、クリック後のCLI結果／タイトル照合／SetParent結果はレポートから判断できない。**
- Monitorレポートは添付ZIPに見当たらず、Snapshotのみ。

## v1.0.3 の実装

- **非同期オープンと本体確認を別々のCLI `eval` に分割。** `main_open_code` で既存のメインleafにノートを1度だけ開く。`main_verify_code` は状態を読むだけで、表示ノートとメインdocumentのタイトルが一致した場合にのみHWND照合へ進む。
- メインDOMが未準備という明確な結果が返った場合のみ、次回のオープン要求を許可。それ以外では12回の確認ループ中にノートオープンを連打しない。
- 旧処理はasync `openFile()` の結果とタイトルを1回のCLI応答に依存。Obsidian CLIに非同期操作後のstdoutが消える報告（1.12.7）あり。ただし **1.15.1での今回の失敗原因と断定できない**。

- `%LOCALAPPDATA%\FRBLaunch\obsidian_dock_trace.jsonl` に、Obsidianの1回ごとの処理を時系列で記録。
- `DOCK_REQUEST` → `PROBE_START` → `CLI_RESULT`（`main_open` / `main_verify`） → `PROBE_RESPONSE` → `CAPTION_MATCH` → `HWND_SELECTION` → `SETPARENT_*` → `BIND_START` → `CLI_HANDSHAKE_COMPLETED`。
- CLI失敗時には、タイムアウト、終了コード、応答行数、受信マーカー数、既知プロトコルの種別を残す。
- Win32側はObsidian.exeの候補について、HWND、PID、Window Class、親/所有HWND、表示/子ウィンドウ属性、**タイトルの長さとハッシュのみ**を記録。
- タイトルの実文字列、Vault ID、ノート名、CLI実行JS、CLI生stdout/stderr、文書本文は記録しない。
- ログが1MBに達したら1世代だけローテーション。外部送信なし。

## 実機確認手順

1. Obsidianのノートを必要に応じて保存し、Obsidian本体をデスクトップに表示。
2. 修正差分を適用してFRB Launch再起動。
3. Files ListでVault内の `A.md` をダブルクリック。第3列に本体が入るか確認。
4. 成功した場合は `B.md` → `A.md` → 第3列×（本体復元）→Launch終了（Obsidian継続）も確認。
5. 失敗した場合は `%LOCALAPPDATA%\FRBLaunch\obsidian_dock_trace.jsonl` を共有。
   これはタイトル等を記録しない診断ログだが、PID/HWNDが含まれるので共有前に内容を確認する。
6. 可能ならInspectorの `[2] Monitor 30 seconds` も同時に実行し、ウィンドウ構造の変化を測る。

**Windows実機・Obsidian CLIとの実通信・SetParentは未検証。** この差分を「本体収容の修正成功」とは扱わず、失敗した境界を実測で特定するための段階とする。
