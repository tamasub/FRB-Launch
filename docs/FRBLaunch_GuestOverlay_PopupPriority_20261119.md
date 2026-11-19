# FRB Launch — Obsidian縁台と検索履歴・パンくず履歴の優先表示

## ベース

`launch_app_20261119_142646.zip` に対する差分。既存環境の `FRB_OBSIDIAN_IME_OVERLAY=1`（`_run_windows_Try_Obsidian_IME_Overlay.bat`）で使用する。通常の `SetParent` 収容、Studio、Browser、サクラエディタは変更対象外。

## 不具合

Obsidian縁台（Overlay）は Windows 上の**独立トップレベルHWND**、メイン検索履歴とパンくず履歴は Launch 内の **QFrame子ウィジェット**。Obsidian HWND を Launch の直前のZ-orderへ配置しても、子QFrameを `raise_()` しただけではObsidianより前には出ない。結果、検索・履歴パネルの右側がObsidianに覆われてクリックできない。

## 修正

1. `guest_popup_occlusion.py` を追加。Qt子ウィジェットの座標を、Win32で取得した第3列ホストの実ピクセル座標へ変換する。高DPIにも対応する。
2. Win32の `SetWindowRgn` と `CombineRgn(RGN_DIFF)` を利用し、**履歴ポップアップと重なる領域だけObsidian側の表示領域から差し引く**。Obsidianの非重複部分は残し、全体を `SW_HIDE` しない。親ウィンドウ・IME・フォーカス・Z-orderは変更しない。
3. 履歴ポップアップの表示・非表示時に即時更新。Launchの移動・リサイズ中は従来の160msタイマーでも追跡する。
4. メイン検索履歴 `history_popup` と、パンくず履歴 `favorite_popup` を対象にする。いずれも実際の可視状態と位置を参照する。重なりがない場合はマスクしない。
5. 履歴を閉じたとき、第三列を閉じたとき、外出し・通常復元時は Win32 領域を解除する。OSに移譲した GDI リージョンを二重解放しない。
6. 同じ配置に対する160msごとの反復ではネイティブAPIを呼ばない（チラつき抑制）。

## 変更・追加ファイル

- `src/obsidian_ime_overlay.py`（Overlayのウィンドウマスクと解除）
- `src/guest_popup_occlusion.py`（新規：DPIを考慮した重なり計算・GDI所有権管理）
- `src/studio_preview_panel.py`（対象ポップアップの相対座標収集・定期更新）
- `src/expanded_view.py`（パンくず履歴の表示・非表示時の即時更新）
- `src/app.py`（検索履歴の表示・非表示時の即時更新）
- `tests/test_guest_popup_priority_20261119.py`（新規：サイズ計算・GDIマスク・復旧・UI接続）

## 検証

- 関連9ファイルのテストを実行：**74 passed、2 skipped**。
- 旧UIの文字列を直接比較するテストで既存失敗が見つかったが、ベースZIPでも同じ失敗（新規回帰ではない）。
- Pythonの構文検査PASS。
- **PySide6/Windows実機描画はここでは実行できない**ため、IMEとWindows合成の最終検証は実機が必要。

## Windowsで確認してほしいこと

1. Overlay起動でObsidianを第3列に表示 → メイン検索履歴を開く。検索履歴の右端まで表示・クリックできるか。
2. 同じくパンくず履歴を開く。前面に表示されるか。
3. 履歴を閉じる。Obsidianの編集画面に「欠けたままの領域」が残らないか。
4. 日本語変換候補が編集カーソル付近に出るか（以前のIME成功を維持）。
5. Chromeを前面にする、Launchに戻す、最大化・移動、Obsidianを外出しする、の動きに回帰がないか。

※この差分は新たにWindowを作ったり、Obsidianを終了したり、Vault設定を書き換えたりしない。
