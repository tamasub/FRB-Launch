# FRB Launch 第3列ゲストクリック問題：Window Inspector Zオーダー診断拡張

- 基準：`launch_app_20261121_212616.zip`
- 対象：`tools/FRB_Window_Inspector/collect_windows.ps1`
- Launch本体・Overlayの動作コードは**変更しない**。Windowsウィンドウ読み取りのみ。

## 背景

`guest_ztrace_latest.log` (2026-11-21) では、Obsidianをクリックした操作で `overlay_raise success=1` / `overlay_synced` が記録されているが、ユーザー画面ではLaunch本体が前面にならない。`above_guest=3278072` の正体や `hit_not_guest` の原因が不明。

## 追加した情報

- TopLevel行に `ZRank` を追加。`EnumWindows` 列挙順を採用し、0が最前面、値が大きいほど背後。Child行は `-1`。
- `zorder_timeline_FOCUS.csv` をSnapshot／Monitorともに出力。Monitorは既存ループの各サンプルで採取。
- 注目アプリ各トップレベル窓の `HWND/PID/プロセス名/クラス/ZRank` と、直前の可視ウィンドウ（HWND、プロセス、クラス）。
- カーソル位置に重なっている、対象よりZオーダーが高いウィンドウ候補（`AboveCursor...`）。
- `WindowFromPoint` からの `HitHWND` とルート `HitRootHWND`、前面の `ForegroundHWND`。対象ウィンドウが見えていても別のウィンドウとしてヒットした事象を検証する。
- `FOCUS.json` と共有用ZIPに新しい診断情報を追加。全件プロセス情報の共有は避ける。

## 再現

1. 第3列にObsidian（次にVSCode、サクラエディター）を表示。
2. Inspector BAT `[2] Monitor 30 seconds` を実行。
3. ChromeをLaunchの手前へ置き、Obsidianの見えている部分をクリックして不具合を再現。
4. Inspectorの `FRB_WindowReport_FOCUS_SHARE.zip` を確認して共有。
5. 同じ試行の `guest_ztrace_latest.log` があれば併せて共有。HWNDとタイムスタンプで照合。

## 注意／未検証

- Win32環境に依存するので**Windows実機動作は未確認**。Linuxでの静的検証のみ。
- `NearestVisibleAbove` は重なっているとは限らない。座標・`HitRootHWND` と合わせて判断する。
- Monitorは250ms標準。クリック直後の瞬間的な変化は取り逃し得る。
- 記録する対象タイトルやプロセス名には機微情報が含まれ得る。共有前にZIP内容を確認する。
