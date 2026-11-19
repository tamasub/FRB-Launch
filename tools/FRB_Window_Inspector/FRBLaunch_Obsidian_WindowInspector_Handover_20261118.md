# FRB Launch × Obsidian × Windows Window Inspector — 高密度引継ぎ

> **作成日**：2026-11-18（JST）／**用途**：新しいChatGPTチャットへのそのまま貼付・ファイル添付。
> **一言要約**：FRB Launchの3列目へObsidianの**ポップアウトではなくVault本体ウィンドウ**を収容したい。最新試作は実機で**本体HWNDを特定できず失敗**。場当たりの再改修を止め、作成済みの汎用Windows Process/Window InspectorでHWND/PID/親子構造を採取し、実測で原因特定する段階。次の標的はVS Code。

## 0. 次チャットへの最優先指示

1. **まず診断ツールの実測レポートを受領・解析する。** コードの推測修正を先行しない。ユーザーからInspectorの`FOCUS_SHARE.zip`が来たら、SnapshotとMonitorの差分で「Obsidian本体HWNDを捕捉できたか／実際に親が変わったか」を調べる。
2. 次にLaunchの現在使用中の**最新フルZIP**をユーザーから受け取る（最後に会話へ提供されたフルZIPは`launch_app_20261118_202041.zip`。その後`FRBLaunch_Obsidian_MainWindow_NoPopout_20261118_diff.zip`を適用してユーザーが失敗を報告した。ユーザーPCにある最新状態の完全ZIPと同一とは限らない）。差分ZIPは必ず**提供された最新フルZIPを基準**に作る。
3. Obsidianについては**外部アプリ／既存ウィンドウ／未保存編集を保護**。適当なHWNDを奪わない、勝手にプロセス終了させない、失敗時に新しい窓を大量生成しない。Studioとサクラエディタ等の既存機能を壊さない。
4. コードを変更する場合、**差分ZIP＋テスト＋実機未検証点の明記**。ユーザーは短い反復、実物評価、軽快さ重視。日本語・砕けた会話は可、未検証を「完成」と断定しない。

## 1. 目標／成立条件

- FRB Launch（Windows 11、Python/PySide6）の**Files Exp → Files List → 第3列**の作業UIを育てている。Files Listで`.md`をダブルクリックすると、**ObsidianのVault本体ウィンドウそのもの**を第3列へ収容したい。
- Obsidian標準の**左サイドバーを閉じる**。ファイル一覧はLaunchのFiles List側で表示するため、Obsidianのファイル一覧は重複する。
- `.md` A→B→C→A：**同じObsidian本体・同じ編集領域でファイルのみ切り替え**。毎回別窓や新規タブを開かない。第3列の×ではObsidian本体を安全にデスクトップへ戻し、Launch終了でObsidianを勝手に終了しない。
- 次のターゲットは**VS Code**。Obsidian固有の手探り実装を繰り返すのではなく、**プロセス、HWND、親子・所有者関係、ウィンドウ出現・消失**を汎用的に調査・再利用する方針。

## 2. 検証済み事実／未解決点【混同厳禁】

### 実機で一度成功したこと

- **旧・ポップアウト方式**（`FRBLaunch_Obsidian_OnePopout_CLI_Trial_20261118_diff.zip`系列）ではユーザー確認で、①**サイドバーが消えた**、②**次のMarkdownを同じ窓に切替**できた。前面ちらつきも当初より減った。
- ただしその方式は**Obsidian本体が別のデスクトップウィンドウに残る**。ユーザーはこれを根本的に不要・設計違いと指摘。ポップアウトは「問題を回避するために別室を増やしていた」誤った方向。
- Studioの第3列収容・外出しはユーザー実機で**脱出成功**（外出し後に単独ウィンドウとして作業可能）。Launch終了後も外出しStudioを維持する設計。Obsidianとは別実装であり、壊さない。
- `/` 矢印メニュー：軽量スクロール、Exp枠内への重ね表示、階層を→で進む操作は概ね好評。無関係な改変不要。

### 最新・本体収容方式の実機不具合

- **最新トライ：`FRBLaunch_Obsidian_MainWindow_NoPopout_20261118_diff.zip`**。ユーザーは`launch_app_20261118_202041.zip`を基準とした差分を適用してテスト。
- 画像：Launchの第3列に「Obsidian本体のウィンドウを一意に確認できませんでした…」相当の待機/失敗メッセージが出ている一方、**Obsidian本体はLaunch外に残り**、別のObsidian窓も外側に見える。**第3列への本体収容は未達**。
- 添付実ログ：`貼り付けたテキスト（1）(20261118-113910).txt`（約78KB）。Obsidian 1.15.1 (`obsidian-1.15.1.asar`)で`obsidian://open/?vault=<id>`を受信。`eval`コマンド（`main_probe_code()`相当）を**同一ファイルへ多数回**受信している。
- ログに出ているのはObsidian側の`argv`と受信コマンドの表示で、**Launch側が受け取ったCLI stdout / returncode / `FRB_MAIN_TITLE:...`の成否は確認できない**。ここを事実と推測で混同しない。
- `sqlite_persistent_shared_dictionary_store.cc ... Invalid total_dict_size detected` はChromium系ログにあるが、**本体収容失敗の因果関係は未確定**。
- コード上、`_probe_obsidian_main_window()`は約450ms待ちを挟んで最大12回の確認。毎回CLI `eval`を打つ構造であり、ユーザーログで同文コマンドが多数見える理由の一部になり得る。
- **現在の最重要未確定点**：CLIが`FRB_MAIN_NOT_READY` / `FRB_CLI_FAILED`を返しているのか、`FRB_MAIN_TITLE:<URLエンコードしたタイトル>`を返しているのにWindowsのHWND/タイトル一致に失敗しているのか、あるいは`SetParent`/埋込段階で失敗しているのか。**Launch側の構造化ログとWindow Inspectorの測定が必要**。

## 3. ソース／成果物の正確な版関係

| ファイル（このチャットで生成・提供済） | 役割／状態 |
|---|---|
| `launch_app_20261118_202041.zip` | **本体収容差分の適用元フルソース**。ユーザーがその後試した基準。最新のユーザーPCの状態とは限らない |
| `FRBLaunch_Obsidian_MainWindow_NoPopout_20261118_diff.zip` | **現在試験中・実機NG**。本体Vaultウィンドウ収容＋CLI確認・`paneType=window`廃止。差分9ファイル |
| `FRBLaunch_Obsidian_OnePopout_CLI_Trial_20261118_diff.zip` | 旧方式。**サイドバー非表示＋次ファイルの同じ窓切替は実機成功**、ただしポップアウトなので本体が外に残る |
| `FRBLaunch_Obsidian_QuietFirstDock_20261118_diff.zip` | 初回の飛び出し低減実験。ユーザー評価で悪化。使わない |
| `FRBLaunch_Obsidian_QuietFirstDock_Rollback_20261118_diff.zip` | 上記を戻す差分 |
| `FRBLaunch_Obsidian_SinglePopup_NoFallback_20261118_diff.zip` | 窓増殖防止試作。**新しい.mdが開けなくなった**とユーザー報告。成功版扱いしない |
| `FRB_Window_Inspector_v1.zip` | **次に使う汎用診断ツール**。`FRB_Window_Inspector.bat` + `collect_windows.ps1` + `README_使い方.md` |
| `FRBStudio_App20261118_184326.zip` | この会話で最後にユーザーから提供されたStudioフルソース（現在の最新版とは断定しない） |
| `FRBLaunch_StudioPreview_QTimer_Hotfix_20261118_diff.zip` | Launchの`_ensure_studio_preview()`内`QTimer`のローカル再インポート起因`UnboundLocalError`修正。Studio本体再ビルド不要 |

**注意**：古い差分を順番に全部重ねてはいけない。次はユーザーPCから**最新の全体ZIP**を受け、実装済の挙動を確認してから差分を作る。次チャットへ添付ファイルが自動で全て引き継がれるとは限らない。

### 本体収容差分で実際に変更されたもの（ZIP収録）

- `src/external_preview_route.py`
- `src/obsidian_dock_bridge.py`（公式CLI、Vault識別、メインDOM leaf探査、ウィンドウタイトル照合）
- `src/studio_preview_panel.py`（第3列・収容状態管理・CLIワーカースレッド）
- `tests/test_obsidian_main_window_dock_20261118.py` ほかObsidian/外部エディター関連テスト
- `docs/FRBLaunch_Obsidian_MainWindow_20261118.md`

### 実装キー（検索用）

- `src/studio_preview_panel.py`：`open_external()`、`_probe_obsidian_main_window()`、`_on_obsidian_main_probe_completed()`、`_fail_obsidian_main_dock()`、`_begin_obsidian_cli_bind()`、`_switch_obsidian_inside()`。
- `src/obsidian_dock_bridge.py`：`find_cli()`（`Obsidian.com`）、`main_probe_code()`（メインの`iterateRootLeaves`/`openFile`/`document.title`）、`main_window_matches_caption()`（**大文字小文字を無視したタイトルの完全一致、かつ一意のHWND**）、`cli_eval()`（stdout解析、タイムアウト5秒）、`bind_main_code()`、`switch_main_code()`。
- `src/external_win32_host.py`：`editor_windows('obsidian', include_hidden=True)`、ウィンドウ列挙関連。
- `src/studio_win32_host.py`：`AttachedStudioWindow(hwnd, host.winId())`、Windows SetParent/resize/detach。
- `main_probe_code`の成功戻り値は `FRB_MAIN_TITLE:` + `encodeURIComponent(document.title)`。失敗側は`FRB_MAIN_NOT_READY` / `FRB_NOT_FOUND`等。`cli_eval()`が複数行CLI出力をどうパースするかも重点確認。

### 設計上の注意

- `paneType=window`は**新しいポップアウト窓**を作るので、本体収容案では使用しない。
- CLIで`window`/`document.title`がどのDOMを指すかは実機検証が必要。Obsidianに複数のBrowserWindow・Vaultがある場合、APIの戻り値とWin32タイトルが一致するとは限らない。
- 「一致しないから適当なタイトルの窓を取る」という安易な修正は禁止。**PID/HWND/プロセス階層/Win32 WindowClass**を測って安全に特定する。
- 第3列の×・Launch終了では既存Obsidianを**終了せずデスクトップへ戻す**。未保存状態を破壊しない。

## 4. 今回作成した汎用Windows診断ツール

**成果物**：`FRB_Window_Inspector_v1.zip`（Windows 11 / PowerShell 5.1 / BAT。読み取り専用。管理者権限通常不要。Windows実機未検証）。

構成：`FRB_Window_Inspector.bat`、`collect_windows.ps1`、`README_使い方.md`。BATダブルクリックでメニュー：

- `[1] Snapshot`：全プロセス＋全トップレベル窓＋注目アプリの子ウィンドウの静的情報。
- `[2] Monitor 30秒`：250ms間隔で新規トップレベル窓・消失・移動・タイトル・表示/前面変化を観測。
- `[3] Monitor 60秒`：上記の長時間版。
- `PID / ParentPID / 実行パス / HWND / ClassName / ParentHWND / OwnerHWND / RootHWND / Visible / DWM Cloaked / WindowRect / Style`等を取得。
- 結果は`reports/FRB_WindowReport_.../`へ出力。`processes_*_ALL.csv`、`windows_*_ALL.csv`、`window_events_ALL.csv`、`FULL_LOCAL.json`（**全件・ローカル用**）、`SUMMARY.txt`、`*_FOCUS.csv`、`FOCUS.json`、`FRB_WindowReport_FOCUS_SHARE.zip`（**共有用**）。
- 既定注目フィルター：`obsidian|code|frb|launch|python|pyw|sakura|notepad`。VS Codeに拡張可能。既定ではコマンドライン引数は収集しない（秘密情報防止）。ネット送信なし・Windowsアプリを起動/移動/終了しない。
- **Windows実機での初回実行は未検証**。短いウィンドウの出現は250msサンプリングで取り逃しうる。`GONE_FROM_TOP_LEVEL`は終了だけでなく`SetParent`による子ウィンドウ化でも発生する。

**ユーザーが今から行う想定の操作**：

1. Obsidian本体とFRB Launchを両方表示して、Inspector BATの`[1] Snapshot`。生成された`FOCUS_SHARE.zip`を確保。
2. `[2] Monitor`を開始後30秒以内に、LaunchのFiles ListでMarkdownをダブルクリックし、「第3列に収容されない」症状を再現。
3. 2つの`FOCUS_SHARE.zip`を新チャットへアップロード。**送信前に文書タイトル・ローカルパスを確認**。全件ALLやFULL_LOCALは原則送らない。
4. もしInspector自身がPowerShellエラーになる場合は、**エラー全文を受け取りInspectorを修正**。このツールはまだWindows実測未検証。

## 5. 診断結果が来た際の解析順（次担当の作業手順）

1. **プロセス分離**：`obsidian.exe`のPID/ParentPID/起動時刻/実行パスと、Launchの`python.exe`等のPIDを把握。Vault本体／既存ポップアウト／Launchの親子・所有者情報を区別する。
2. **Windows構造のbefore/after**：注目Obsidian HWNDごとに、WindowClass、タイトル、Visible、ParentHWND、OwnerHWND、RootHWND、rectを比較。`NEW_TOP_LEVEL`と`GONE_FROM_TOP_LEVEL`の変化を確認する。
3. **CLI応答を測る**：`main_probe_code()`の実際のCLI **returncode/stdout/stderr、パース後のresult、試行番号、所要時間**をLaunch側で1回につき1レコード記録（必要なら新たな診断ログを追加）。Obsidianのコマンド受信ログだけでは結果は分からない。
4. **判定分岐を明示**：`FRB_MAIN_NOT_READY`ならJS root-leaf検出条件、`FRB_CLI_FAILED`ならCLI stdout/パース/タイムアウト、`FRB_MAIN_TITLE:...`ならWin32タイトル照合・重複・プロセスID、HWND一致後ならSetParent/サイズ・Win32エラー情報を疑う。
5. **ログの質**：無意味なCLI連打や窓操作の追加は避ける。時系列（timestamp/attempt/target note/CLI result/HWND candidate/decision/error）を構造化する。ローカルパスや全JSコードの多重出力は抑制し、必要時だけ全件ログへ残す。
6. **修正後の合格試験**：初回A.md本体収容→左サイドバーが閉じる→B.md/C.md/A.mdの繰返し→ウィンドウの増殖なし→第3列×で本体が元のデスクトップへ復元→Launch終了でもObsidian本体維持。別Vault・複数窓・収容失敗の安全性も検証。

## 6. FRB Launchの維持すべき既存仕様（最低限）

- Files UI：Exp（フォルダー/仮想ツリー）、List（ファイル・URL・JSON・Markdown等）、第3列（Studio/Obsidian/サクラ/ブラウザ系）。**Files Listの既存判定を再利用**し、種類ごとに勝手に実行経路を分岐増殖させない。
- `/` メニュー：Exp枠内に重ねる。各列検索欄、↑↓で軽快に固定枠内スクロール、→で子階層、←で戻る、枝のEnterは動かず**末端Enterだけ実行**。末端→はコンテキストメニュー。`/`やEscで閉じる。フォルダー中だけ「（カレントフォルダー）」→コンテキスト、Expルートには出さない。
- 幅：通常270px／長い名前あり380pxを基準に、必要ならExp内幅へ収める。アイコン整列・▶右寄せ・長い名称省略。細部は最新ソース優先。
- Listで`Shift+↑↓`の複数選択。単一行専用の「簡易編集」等は複数選択時無効化。ぐりぐり（Exp/List）ボタンは第3列開閉で位置ずれしない。
- FRB Studio：JSONダブルクリック→第3列NativeShell、必要なら外出し（Browserと同型アイコン）。外出し後は独立プロセスとして作業。WebView2領域競合対策、SilentDockおよびQTimerローカルimport例外の修正履歴あり。別途動いている動線は守る。
- Obsidian本体収容・サクラエディタ等のWin32 HWND制御は**他のアプリに波及しない責務分離**を徹底。

## 7. 開発・納品ルールと次チャットへの短い開始文

- ユーザーはWindows11/PowerShell/Python/VS Codeで実動作を確認。完成品は**差分ZIP**希望。テストは失敗ゼロと断言せず、変更前baselineとの差分で新規劣化を確認。LinuxコンテナにPySide6/Win32 GUIがない場合は**静的・模擬テストのみ**と必ず明記。
- 以前の改善は「動いた部分が実機で動いた」事実を尊重し、既存動線を安易に捨てない。UIの軽さを優先し、むやみにポーリング・前面化・新窓生成を追加しない。
- コードを変更する前に**対象ZIPを必ず開いて検証**。差分の適用元・変更ファイル・テスト件数・実機未確認点を明示。

**次チャットでの最初の依頼例**：

> これはFRB Launchの引継ぎMDです。Obsidian本体収容がまだ失敗しています。汎用`FRB_Window_Inspector_v1`を作ったので、まずSnapshot/Monitorのレポートを解析して、本体HWND/PID/親子構造、CLI戻り値の不足、収容失敗箇所を切り分けてください。推測でポップアウトや前面操作を増やさないでください。VS Code連携にも再利用できる診断・収容基盤を意識してください。

---

**判断軸**：実測を先に／動いた機能を壊さない／ユーザーのデータ・外部アプリを保護／余計なウィンドウを作らない／将来VS Codeへ横展開できる設計。
