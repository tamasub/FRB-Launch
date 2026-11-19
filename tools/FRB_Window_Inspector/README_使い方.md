# FRB Window / Process Inspector v1.0

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
| `*_FOCUS.csv`, `FOCUS.json` | Obsidian、VS Code、Launch、Python等に絞った共有用データ |
| `SUMMARY.txt` | 注目アプリのウィンドウ構造を読みやすく整理 |
| `FULL_LOCAL.json` | 今後の比較・スクリプト解析用の全件構造化データ |
| `FRB_WindowReport_FOCUS_SHARE.zip` | **共有用**の注目アプリデータのみ圧縮。全件のプロセス一覧は含めません |

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
- 共有用ZIPもローカルパスや編集中の文書名を含む可能性があります。内容を確認してから送ってください。
- 管理者権限がないプロセスは、実行パス等の一部が空欄になることがあります。これは正常です。
- Monitorは250ms間隔で観測します。もっと短い瞬間のウィンドウは取り逃す可能性があります。
- `GONE_FROM_TOP_LEVEL` は終了だけでなく `SetParent` による子ウィンドウ化でも発生します。最後の `windows_after_ALL.csv` で判断します。
- Win32 API／PowerShellを使っています。**Linux環境では動作テストできていないため、Windows実機の最初の実行で確認**してください。
