# FRB Window / Process Inspector v1.0（Zオーダー診断拡張）

**Windows 11 / Windows PowerShell 5.1 向け、読み取り専用の汎用診断ツール**です。Obsidianだけでなく、VS Code、FRB Launch、FRB Studio、ほかのWindowsアプリにも使えます。アプリの設定やウィンドウ状態は変更しません。管理者権限も通常は不要です。

## 使い方

1. ZIPを解凍し、`FRB_Window_Inspector.bat` をダブルクリック。
2. `[1]` はその瞬間の**全プロセス・ウィンドウ一覧**を取得。
3. `[2]` は**30秒間**、新しいウィンドウ、消失、移動、表示状態、前面の変化を記録。実行開始直後にLaunchでMarkdownファイルをダブルクリックしてください。`[3]` は60秒間。
4. `reports/FRB_WindowReport_.../` に結果を保存。`FRB_WindowReport_FOCUS_SHARE.zip` を中身確認後に、このチャットへ添付してください。

**今回のObsidianなら**、まずObsidian本体とLaunchを両方表示した状態で `[1]` を1回。続いて `[2]` を選び、30秒以内にLaunchからMarkdownを開いてください。2つの `FOCUS_SHARE.zip` を送ってもらえば「本体のHWND / PID / クラス」と「第3列への取り込み時にトップレベル→子ウィンドウへ変化したか」を比較できます。

## 取得するデータ

| ファイル | 内容 |
|---|---|
| `processes_*_ALL.csv` | 全プロセスのPID、親PID、実行ファイルのパス、起動日時、メモリ量など |
| `windows_*_ALL.csv` | 全トップレベルウィンドウ＋対象アプリ配下の子ウィンドウ。HWND・PID・タイトル・ClassName・Visible・親／所有者／Root HWND・矩形・スタイル・DWM Cloakedなど |
| `window_events_ALL.csv` | Monitor限定。新規ウィンドウ、トップレベルからの消失、移動・表示状態・タイトル・前面切替 |
| `zorder_timeline_FOCUS.csv` | **追加**。Snapshotで1回／Monitorで約250msごとに、注目アプリのZオーダー順位・前面・クリック位置の実際のウィンドウ・直上のウィンドウを記録 |
| `*_FOCUS.csv`, `FOCUS.json` | Obsidian、VS Code、Launch、Python等に絞った共有用データ |
| `SUMMARY.txt` | 注目アプリのウィンドウ構造を読みやすく整理 |
| `FULL_LOCAL.json` | 今後の比較・スクリプト解析用の全件構造化データ |
| `FRB_WindowReport_FOCUS_SHARE.zip` | **共有用**の注目アプリデータ＋Zオーダーの隣接ウィンドウ情報を圧縮。全件のプロセス一覧は含めません |

### 第3列ゲストの「クリックしてもLaunch本体が前に出ない」現象を調べる手順（2026-11-21）

1. **診断対象の最新版Launchを起動**して、Obsidian・VSCode・サクラエディターのどれかを第3列に表示。
2. `FRB_Window_Inspector.bat` を起動して `[2] Monitor 30 seconds` を開始。
3. 30秒の間に、ChromeなどをLaunch本体の上に置き、**第3列のゲストの見えている部分をクリック**。Launchが前に出ないことを確認。
4. Monitor終了後、`reports/FRB_WindowReport_Monitor_.../FRB_WindowReport_FOCUS_SHARE.zip` を、中身の個人情報を確認してから共有。
5. 可能なら同時刻の `guest_ztrace_latest.log` も共有。`guest=...` / `launch=...` のHWNDを `zorder_timeline_FOCUS.csv` に照合できる。

**見る列**：`HWND`、`ZRank`（0が最前面）、`NearestVisibleAboveHWND` とそのProcess/Class、`AboveCursorHWND`、`HitRootHWND`、`ForegroundHWND`。これで「成功扱いなのに何が上にいるか」と「クリック対象が何に見えていたか」を切り分ける。`NearestVisibleAbove` は必ずしも実際の遮蔽物ではないので、`HitRootHWND` とカーソル位置も併用する。

**注意**：従来のMonitorは約250ms間隔。クリックの一瞬を完全に捉えられる保証はない。短時間で戻る現象は引き続き `GUEST_ZTRACE` と時刻で照合する。

### 特に今回見たいポイント

- `Obsidian.exe` と `python.exe`（Launch）のPIDがどれか。
- Obsidian本体のHWND・ClassName、Visible、OwnerHWND、ParentHWND。
- 収容後の `ParentHWND` と `RootHWND` がLaunch側へ変わったか。
- `NEW_TOP_LEVEL` が何回起き、`GONE_FROM_TOP_LEVEL` に変わるか。
- 別ウィンドウが既存の本体なのか、ポップアウトなのか。

### オプション：対象アプリを変更

VS Codeなどを重点確認する場合、PowerShellで次のように実行できます。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\collect_windows.ps1 -Mode Monitor -DurationSeconds 30 -FocusRegex 'obsidian|code|frb|launch|python'
```

デフォルトは `obsidian|code|frb|launch|python|pyw|sakura|notepad` （大文字小文字を無視）。Windows全件のCSVはフィルターにかかわらず取得されます。

`-IncludeCommandLine` を付けると各プロセスのコマンドラインも収集しますが、**認証情報や秘密の引数が含まれる可能性があるため通常は使わない**でください。既定ではコマンドラインの収集・保存を行いません。

## 安全性・注意

- **読み取り専用**。プロセスの終了、起動、ウィンドウの移動、サイドバーの変更は一切しません。
- ネットワーク通信・自動アップロードは一切しません。
- 全件ログにはプロセス名、実行パス、ウィンドウタイトルなどが入るため、**共有しないでローカル保存**してください。
- 共有用ZIPもローカルパスや編集中の文書名、Zオーダーで隣接する他アプリのプロセス名やクラス名を含む可能性があります。内容を確認してから送ってください。
- 管理者権限がないプロセスは、実行パス等の一部が空欄になることがあります。これは正常です。
- Monitorは250ms間隔で観測します。もっと短い瞬間のウィンドウは取り逃す可能性があります。
- `GONE_FROM_TOP_LEVEL` は終了だけでなく `SetParent` による子ウィンドウ化でも発生します。最後の `windows_after_ALL.csv` で判断します。
- Win32 API／PowerShellを使っています。**Linux環境では動作テストできていないため、Windows実機の最初の実行で確認**してください。


## 2026-11-21 追加: Overlay と Chrome の TOPMOST を確認

第3列の Obsidian / VSCode / サクラエディターをクリックしても Launch が Chrome の裏に残る場合は、
**[2] Monitor 30 seconds** で再現して `FRB_WindowReport_FOCUS_SHARE.zip` を共有してください。
**診断の間は Launch やエディターを閉じずに、まず Chrome → 見えているエディター部分のクリックを再現**します。

`zorder_timeline_FOCUS.csv` に次の読み取り専用の情報を追加しています。

- `Topmost`, `ExStyle`: 監視対象ウィンドウ自身の `WS_EX_TOPMOST` と拡張スタイル
- `NearestVisibleAboveTopmost`, `NearestVisibleAboveExStyle`: 手前の可視ウィンドウの属性（Chrome 等）
- `NearestOverlappingAboveProcess`, `NearestOverlappingAboveTopmost`, `NearestOverlappingAboveExStyle`: **画面上で領域が重なる**最も手前のウィンドウの属性
- `AboveCursorTopmost`, `ForegroundTopmost`: マウス位置とアクティブウィンドウの属性

`Topmost=True` は Win32 の `WS_EX_TOPMOST (0x00000008)` を意味します。
ただし、矩形の交差だけでは実際のピクセル遮蔽を保証できません。
Inspector はウィンドウ順を一切変更しません。既存の Snapshot / Monitor 操作方法は同じです。
**個人情報**: ウィンドウのタイトル、プロセス名などは共有前に確認してください。
