# FRB Launch — サクラエディタ第3列 Overlay 修正版（2026-11-19）

## 前回差分の不備と今回の修正
- 前回の差分ZIPには `src/guest_window_overlay.py`（`SakuraGuestOverlay` の定義）が入っていませんでした。今回は含めています。
- 共通オーバーレイの幾何・Z順制御は変更せず、サクラエディタだけ **Windows標準タイトルバー（WS_CAPTION）を保持**します。
- `WS_CHILD` / `SetParent` はサクラの新しいOverlayルートでは利用しません。離脱時は元のウィンドウスタイルに戻します。
- Obsidian・VS Codeのタイトルバーポリシーは従来どおり。`state.ini` と本番ビルドBATは変更していません。

## 試験手順
1. **Launchを完全終了**（二重起動させない）。編集中のファイルは保存してください。
2. このZIPを **FRB Launchルートに相対パス維持で上書き**。前回ZIPを入れた場合もこのZIPだけで不足ファイルを補えます。
3. `_run_windows_Try_Sakura_Overlay.bat` から起動します。通常の `_run_windows.bat` は使わないでください。
4. Files Listから `.txt` を1個開き、**サクラのWindows標準タイトルバーが見える**か確認します。
5. 別の `.txt` を開いて同じタイトルバーが維持されるか確認します。さらにタブ／別HWNDが生成される場合の動作を確認します。
6. 「外に出す」、×→再表示、編集・保存、日本語入力、リサイズを確認してください。

## 重要：FRBStudio.NativeShell の WebView2 例外
報告の `CoreWebView2Controller members cannot be accessed after ... disposed` は **FRBStudio.NativeShell.exe** の例外です。このLaunch差分はそのC#プロセスを修正しません。
切り分けのため、まず**Studioを表示していない状態**でサクラだけの「1個目→2個目」を試してください。Studioと交互に切り替えた際にだけ再現する場合、Studioのウィンドウ再親子化（`SetParent`）と WebView2 のハンドル再生成のライフサイクルを別途検証する必要があります。StudioのNativeShellソースは添付されておらず、その問題は未修正です。

## 安全境界と現状
- Launch起動前からあるサクラの既存ウィンドウは自動取り込みしません。
- サクラ側が既存タブへ開き直して新規HWNDが出ない場合、取り込みはタイムアウトになることがあります。
- ×は編集データを捨てず、非表示で保管します。終了/保存はアプリ側で行ってください。
- ローカルの自動テストでは、サクラのネイティブタイトルバー保持、スタイル復元、既存Overlayの表示互換性を確認。**Windows/Sakura/Studio実機での保証ではありません**。
- ユーザーの実環境でのコードがどの版で動いているかは、このZIPを適用して再確認が必要です。
