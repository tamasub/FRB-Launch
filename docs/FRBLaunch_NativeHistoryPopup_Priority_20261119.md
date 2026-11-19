# FRB Launch — メイン検索履歴／パンくず履歴の前面化（2026-11-19）

## 適用基準
- `launch_app_20261119_151044.zip` のLaunchルートへ差分を上書き。
- Studio / Obsidian は変更・再ビルド不要。
- 実機未検証のWindows/Qt試作改修。必ず元ZIPを保存してから適用。

## 原因と実装
- **原因:** メイン検索履歴とパンくずフォルダー履歴はLauncher内の `QFrame` 子ウィジェット。Obsidian Overlayは独立したネイティブHWNDなので、Qtの `raise_()` では子フレームをOverlayより前に表示できなかった。
- **今回:** 2つの履歴を `Qt.Tool | FramelessWindowHint` 付きの *Launcher所有のトップレベルQtウィンドウ* とする。`Qt.Popup` のようなキーボード／マウスの強制grabはしない。元の検索欄／ツリー／Ctrl+G／Remoteのキーフォーカスは維持する意図。
- 2つのポップアップの座標は、従来のLauncher内配置計算を保持したまま `mapToGlobal` で**画面座標**に変換。Launchの移動・リサイズ時にも再配置。
- Obsidian Overlayへの `SetWindowRgn`（表示領域切り抜き）の呼び出しを廃止。代わりに表示中の履歴トップレベルHWNDを確認し、Win32の `SetWindowPos` の挿入順序で **Popup > Obsidian > Launch** を狙う。
- ポップアップのHWNDとLaunchのHWNDの最前面ティア（TOPMOST / 通常）が異なる場合、Obsidianを誤ってTOPMOSTへ昇格させない。
- Launchアプリが非アクティブになったら2つの履歴を閉じる。従来のLaunch内のクリック・選択・Escによる閉じ方は維持。
- フォルダー検索履歴（既存 `QMenu`）は変更しない。Obsidianの `SetParent`／IME／CLI／第3列のファイル切替も変更しない。

## 検証
- 専用テスト9件PASS（ネイティブウィンドウ指定、画面座標、フォーカス喪失時の閉鎖、Win32モックでPopup/Guest/LaunchのZ-order、TOPMOST保護、Launch移動追従）。
- Obsidian Overlayと既存優先表示関連を含む集中テスト34件PASS（専用9件のうち前段階の8件を含む）。
- 広範囲の対象テスト：116 PASS / 11 SKIP / 16 FAIL。元ZIPでも同じ16 FAILで、新しい失敗は0（対象は旧UI前提のテストと既存モックエラー）。旧「切り抜き」前提の1テストと、旧ローカル座標前提の1テストは新仕様へ更新した。
- Python構文検証PASS。**PySide6が環境にないためQt/Windows画面の実機確認は未実施。**

## Windows実機での確認手順
1. `_run_windows_Try_Obsidian_IME_Overlay.bat`（実際に使っているOverlayモードBAT）でLaunchを起動し、.mdを第3列に表示。
2. メイン検索履歴を開く：履歴一覧がObsidianの前に**全体表示**され、スクロール、検索、選択が正常か確認。
3. 履歴を閉じてパンくず履歴を開く：同様に全体表示・選択が正常か確認。
4. 履歴を開いたままChromeを前面化：履歴が自動で閉じるか確認。戻ったらObsidianが第3列に残るか確認。
5. Launch移動／最大化でポップアップ位置が追従するか確認。
6. Obsidianで日本語変換：IME候補が編集カーソル付近に出ることを確認。
7. 元に戻したい場合は、基準ZIPから本差分の改修ファイルを戻す（または基準ZIP全体で復元）。

## 注意
- `Qt.Tool` のネイティブフォーカス挙動とWin32オーナーウィンドウの重なり方はWindows実機での最終判定が必要。
- 不具合が残れば、まず履歴を開いた状態の `HWND` 順序と `TOPMOST` フラグをFRB Window Inspectorで計測する。別の `SetWindowRgn` 補正を足さない。
