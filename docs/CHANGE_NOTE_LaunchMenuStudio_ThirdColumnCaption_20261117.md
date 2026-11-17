# FRB Launch 第3列：メニュー設定ウィンドウ収容の修正（2026-11-17）

## 対象

前回配布差分 `FRBLaunch_StudioThirdColumn_SettingsHide_20261117_diff.zip` 適用後のFRB Launch。
今回の修正は `src/studio_win32_host.py` のみ。Studio C#のソース、JSONデータ、保存機能には変更なし。

## 現象

「オプション設定」は第3列に表示されるが、「メニュー設定 (FRB Studio)」は第3列のヘッダーのみ表示され、編集画面が別ウィンドウとして開く。

## 原因

Launchのメニュー設定で起動したC# NativeShellは、通常起動時の `FRB Studio / Native Shell` とは異なり、WebViewのLaunch用プレゼンテーション適用後に `FRB Launch — 設定` にタイトルを切り替える。
既存の `find_studio_main_window()` は通常タイトルとの完全一致のみでウィンドウを探索していたため、設定画面の実ウィンドウを検出できなかった。

## 変更

- ウィンドウ検出の完全一致対象に `FRB Launch — 設定` を追加。
- PID一致、可視、ShowInTaskbarの準備（WS_EX_APPWINDOW）、不透明度200以上という既存の安全ガードを保持。
- スプラッシュ画面や無関係なウィンドウを誤って収容しない。
- 第3列の ×、別ファイル切替、既存C#保存、オプション設定、Browser Previewの処理は変更しない。

## テスト

- 新規のWin32検出モックテスト5件：PASS。
- Studio第3列関連など33件：PASS。
- 関連範囲を広げた62件：60 PASS／2 FAIL。失敗2件は元の前回配布ソースでも再現するもので、旧UI文字列に依存するテスト、および配布されない `config/frb_launch_data.json` を前提とするテスト。
- Python compileall：PASS。
- Windows実機の操作（C# NativeShell収容・編集保存）については未検証。

## Windowsでの確認手順

1. Launchを再起動。設定メニューから「メニュー設定 (FRB Studio)」を選択する。
2. C#画面が外へ飛び出さず、**第3列にメニュー設定が表示される**ことを確認する。
3. テスト用データ（バックアップ推奨）を編集、Studioの既存「保存」で保存し、再読込後も保持されることを確認する。
4. 第3列の×で閉じ、再度メニュー設定を開く。編集状態が保持されることを確認する。
5. 「オプション設定」と通常のJSON／Markdownダブルクリックの第3列表示、およびURL Browser Previewに回帰がないことを確認する。

※このパッチは以前の第3列差分を上書きする追加差分です。以前の差分を未適用の場合は、先に適用してください。
