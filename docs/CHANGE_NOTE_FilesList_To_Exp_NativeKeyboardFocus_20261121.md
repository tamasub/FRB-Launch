# FRB Launch — 「Exp列へ戻る」後のキーボードフォーカス修正

更新日：2026-11-21  
入力資材：`launch_app_20261121_171623.zip`

## 症状

Files Listのコンテキストメニューで「Exp列へ戻る」を選択すると、Exp欄の操作対象表示は切り替わるのに、キーボードの ↑↓ は引き続きFiles List側で処理される。

## 原因

共通ディスパッチ `_dispatch_files_column_context_navigation()` は `remote_focus_area('files_exp')` で**論理操作対象**を更新していた。しかし、`remote_focus_area()` はRemote操作を考慮し、Expの**ネイティブQtキーボードフォーカスを意図的に奪わない**実装である。従って、メニューで明示的に列を戻しても、以前のListのキー受信先が維持されていた。

## 対応範囲

- メニューの「Exp列へ戻る」（ターゲット `files_exp`）完了時のみ、論理操作対象の変更後、実際のExpツリーへ `setFocus(ShortcutFocusReason)` を行う。
- Expが独立したQt.Toolウィンドウの場合は、先にそのウィンドウを `activateWindow()` する。
- コンテキストメニューを閉じた後の既存 `QTimer.singleShot(0, finish)` 内でフォーカスを移す。
- 「List列へ進む」の処理、通常のRemote操作、マウスポインター追従、ファイル／フォルダーの選択・移動処理は変更しない。
- 前回の `Insert` ワープとWindows `MenuKey` 無効化は変更しない。

## 確認

1. Listで適当な行を選択し、コンテキストメニューから「Exp列へ戻る」を実行する。
2. Expでカレントが表示されることを確認し、↑↓でExpの行が動き、Listの行が動かないことを確認する。
3. 独立Expウィンドウ利用時も同様に確認する。
4. 「List列へ進む」、`Insert` ワープ、Windows MenuKey無効化が従来どおりであることを確認する。

自動テストはQt非依存のメソッド抽出テストでフォーカス呼出し順を確認。Windows上の実GUI操作は未実施。
