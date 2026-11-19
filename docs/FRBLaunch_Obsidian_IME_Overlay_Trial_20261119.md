# FRB Launch — Obsidian IME 左上表示対策（非親子化実験）

- 基準: `launch_app_20261119_133020.zip`
- 種別: **実験（Windows実機検証前）**。既存の通常起動では動作を変えない
- 範囲: **Obsidian本体を第3列に表示する際のWin32ウィンドウ管理だけ**
- 変更対象: `src/studio_preview_panel.py`、新規`src/obsidian_ime_overlay.py`、専用起動BAT、テスト
- Studio/C#、Browser、Sakura、Exp Keyborder、JSONデータの変更なし

## 根拠

既存のFRB Window Inspectorモニタ（2026-11-19 13:25～13:26）では、Obsidian の `Chrome_WidgetWin_1` が Launch第3列の子ウィンドウとして正常な画面座標にある一方、Obsidianプロセスの `CiceroUIWndFrame`（日本語未確定入力に関連）がウィンドウサイズを変えながら左上 `(0,0)` に留まった。Obsidian単独起動ならIME位置は正常。

**推定**: Win32 `SetParent` による他プロセスの子ウィンドウ化で、Electron/ChromiumのIME座標管理が矛盾している可能性。現段階では原因は未確定。

## 今回の実験

従来の親子化 `AttachedStudioWindow` は残す。一方、専用BATから起動したLaunchに限り、Obsidianに対しては `ObsidianImeOverlay` を選択する。

- **Obsidian の HWND を `SetParent` しない**。Obsidian本体はWindows上のトップレベルとして維持
- タイトルバーを一時的に外し、Launch第3列のQtネイティブホスト領域へ画面座標で重ねる
- Launch全体の移動・幅変更・最大化・第3列の表示切替に合わせ、約160msごとに位置を同期
- LaunchやObsidian以外が前面になったら、重なりを減らすためOverlayを一時非表示
- Launchが最前面モードでも第3列に表示できるよう、Overlay表示時はWin32最前面レイヤを使用。非表示／終了時は元に復帰
- 第3列×、ほかのファイルへの切替、Launchの正常終了時は、Obsidianの親子関係に触れず元の枠・位置・最前面設定に戻す
- 失敗時もObsidianプロセスへの `kill` や `WM_CLOSE` は送らない

### 試し方

1. Obsidianの編集中ファイルは保存しておく（実験モードのため）
2. Launchを一度終了する（トレイに残っている場合も終了）
3. **`Try_Obsidian_IME_Overlay.bat`** をダブルクリックしてLaunchを起動
4. LaunchからVault内のMarkdownをダブルクリックして第3列表示
5. Obsidian内でかな入力し、**未確定文字／変換候補がカーソルの近くに出るか**を確認
6. Launch全体をドラッグ、最大化・復元、第3列×、別MDを開く操作を確認
7. 不調ならLaunchを正常終了し、従来の **`_run_windows.bat`** から起動し直す（設定変更は不要）

### 実機評価の合格条件

- IME候補が第3列の編集カーソル付近に表示される
- A.md→B.mdの切替成功／Obsidianのウィンドウを増やさない
- Launch移動・サイズ変更・第3列最大化・×でObsidianが消えたり残留したりしない
- Studio、Browser、Sakura、Exp Keyborderとぐりぐりの挙動が従来どおり

### 制約・重要な注意

これは**見た目を第3列に重ねる方式であり、厳密にはQtの子ウィンドウではない**。Windowsの最前面順序、Obsidian内のモーダルダイアログ、Alt+Tab、DPI倍率差、別モニター移動では挙動に制約があり得る。**実機でIME改善が保証されたわけではない**。問題があれば実験モードを停止して通常起動へ戻す。

Windowsのタスクマネージャー等でLaunchを**強制終了**させた場合、Pythonの終了処理が走らず、Obsidianがボーダーレスのまま残る可能性がある。その場合Obsidianの編集内容を保存して**Obsidianだけ正常終了して再起動**して復旧する。Launchを正常終了した場合は元スタイルに復旧するよう実装。

## 検証

- 構文チェック: PASS（Linux上のPython）
- Win32モックによる専用テスト: 7件PASS（親子化なし、座標移動追従、背面化、Launch最小化、設定復元など）
- Obsidian・Studio関連テスト: 83件PASS、3件FAIL。3件の失敗は添付元ZIPの同一テストでも発生する旧仕様前提の失敗。新規失敗0件
- Windows11実機の Qt／Electron／IME 挙動は**未実施**。実験前に「IME改善済み」と断定しない

## 次の観測

実験が失敗した場合は、従来版の `FRB Window Inspector` の Monitor（30秒）を**先に起動**し、第3列で日本語入力したまま監視終了まで維持。`CiceroUIWndFrame` が `(0,0)` のままなのか、今回のトップレベル方式ではカーソル付近へ移ったのかを比較すると、原因を絞れる。
