# FRB Window Inspector — TOPMOST・重なり調査 (2026-11-21)

基準: `launch_app_20261121_214239.zip`

## 背景と未確定な点

過去のInspectorでは Obsidian (Foreground) の前に Chrome が Z オーダー上存在した。
Overlay は `SetWindowPos(root, HWND_TOP, ..., SWP_NOACTIVATE)` を実行するが、
HWND_TOP では TOPMOST グループの窓を追い越せない。Chrome が TOPMOST かどうかは
従来の FOCUS 出力には記録されておらず、根本原因はまだ断定不可。

## 今回の変更

- `tools/FRB_Window_Inspector/collect_windows.ps1`: Win32 拡張スタイルから
  WS_EX_TOPMOST を読み取り、対象・直上・矩形重なりのある直上・カーソル上・前面の窓ごとに記録。
- Inspector README に採取方法を記載。既存メニュー [1], [2], [3] 変更なし。
- 新しい静的契約テストを追加。
- Launch / エディターの実行時コード、Z オーダー制御は一切変更なし。

## 実機確認

`FRB_Window_Inspector.bat` → [2] Monitor 30 seconds。
Chromeを前面に置き、第3列の Obsidian の見える部分をクリックする。
作成された `FRB_WindowReport_FOCUS_SHARE.zip` と、可能なら同時刻の
`guest_ztrace_latest.log` を提供。

`zorder_timeline_FOCUS.csv` の `NearestOverlappingAboveProcess=chrome` と
`NearestOverlappingAboveTopmost=True/False` をまず比較する。
False の場合は TOPMOST 仮説は否定方向となり、Overlay の同期競合を中心に調べる。
True の場合は、クリック時にのみ TOPMOST へ移動するポリシーと
他アプリへ切替時の解除責務を別途検討する（この版では変更しない）。

注: Windows PowerShell / GUI の実機テストは Linux 環境では未実施。
