# FRB Launch — 外部アプリの前後関係と外出し（2026-11-19）

基準ZIP：`launch_app_20261119_135407.zip`

## 目的・決定済みの仕様

- ObsidianはIMEの正常動作を保つため、**SetParentを使わない**既存のOverlay実験モードを維持。`Try_Obsidian_IME_Overlay.bat` で起動した場合だけ適用する。通常起動の実装方式は変更しない。
- 「縁台のObsidian」とLaunchは、他のトップレベルウィンドウに対して同じ前面順序のグループとして振る舞う。Chrome等がLaunchより上ならObsidianだけ飛び出さない。ChromeがLaunchの一部を覆う場合、Obsidianもその覆われた領域だけ自然に隠れる。Launchが最小化・第3列を非表示にしたらOverlayも非表示。
- 「Obsidian外出し」ボタンは第3列の`×`の左隣。クリックするとオリジナルのスタイル・位置に戻し、LaunchのOverlay追従管理を解除、編集内容を破棄せずObsidian本体を独立利用できる。
- Browserでもヘッダーボタンを同じ `最大化 | 外出し | ×` 順にする。Browserの外出しは**現在ページのURLを既定ブラウザで開く**（Launch内部のBrowser Webタブは維持）。アプリ本体の移動ではない。
- FRB Studio／サクラエディタの既存の外出し実装やEditor起動方法は変更しない。

## 変更

1. `src/obsidian_ime_overlay.py`：外部アプリのフォーカス取得による強制 `SW_HIDE` をやめ、Launch直前のWin32 Z-orderへOverlayを配置。`HWND_TOPMOST` の常用を廃止し、Launchと同じZ-order tierへ配置。前景のユーザー選択を `SWP_NOACTIVATE` で保持。160msポーリングで変化がなければWin32位置操作を呼ばない。
2. `src/studio_preview_panel.py`：Obsidianでも既存の外出しボタンを表示し、CLI処理待ち中は無効化。操作時は `detach(foreground=True, show_window=True)` → 管理状態解除 → 第3列を隠す。`WM_CLOSE` 送信・Obsidianプロセス終了はしない。
3. `src/browser_preview_panel.py`：Browserヘッダーに外部表示ボタンを追加。内側Browserの重複アイコンを非表示にし、既存 `LaunchWebView.open_external()` を利用。
4. `tests/`：Win32モックで外部アプリ前景・Launch選択時・Obsidian選択時・最大化/最小化・ウィンドウ移動・外出し状態遷移とヘッダーボタンを検証。旧Overlayの「Chromeを選んだら非表示」というテスト期待値を新仕様に更新。

## 動作確認の推奨シナリオ（Windows 11実機）

1. `Try_Obsidian_IME_Overlay.bat` でLaunch起動。`.md` を第3列に開き、IME変換候補がカーソル近くに出るか確認。
2. ChromeをLaunchの一部に重ね、Chromeをクリック。Chromeが前で、Launchの見えている部分のObsidianは表示されたままであることを確認。
3. Launchをクリック → LaunchとObsidianが前に出る。Obsidianをクリック → ObsidianにキーボードフォーカスがありLaunchも背後に揃う。
4. Launchの移動、最大化、最小化/復帰、第3列の`×`を確認。最小化中にObsidianのみ出現しないことを確認。
5. Obsidianの外出し（`×`左）。独立Obsidianとして入力可能・Launch終了後も継続可能か確認。
6. URLを第3列に開き、Browser外部表示（`×`左）。既定ブラウザへ開き、Launch内のWebタブがそのまま残るか確認。
7. Studioの外出しを再確認。

## 自動検証と制約

- 専用および関連テスト：74 PASS。
- 追加の広範囲テスト：163 PASS / 4 FAIL。4失敗は基準ZIPでも同一（旧仕様を前提とするテスト）。今回追加の失敗は0。
- Python構文チェックPASS。Linux上のWin32モック検証であり、**Windows実機のクリック・IME・Z-orderは未検証**。
- Overlayは厳密な子ウィンドウではないため、特殊な最前面アプリやWindowsダイアログ、複数モニタ/DPI混在では表示順に差が出る可能性がある。何かおかしければ通常の `_run_windows.bat` を使い、従来方式に戻す。
