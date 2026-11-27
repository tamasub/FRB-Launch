# FRB Launch リリース管理 GUI：本体バージョン更新とビルド

基準：launch_app_20261127_202822.zip、および個別添付の _★release_FRBLaunch_GUI.ps1。
差分 ZIP を Launch ソースルート（src、scripts、_build_windows.bat のある場所）に上書き展開する。

## 操作
1. 従来どおり _★release_FRBLaunch_GUI.ps1 を起動する。
2. 上段で本体の更新区分を選ぶ（初期値はパッチ）。①を押すと src/app_version.py の APP_VERSION だけを更新し、既存 BAT でビルドする。据え置きでは書き換えない。
3. 本体ビルド後は据え置きに戻る。再ビルドでは勝手に加算しない。書き込み後のビルド失敗時も更新した版を維持し、据え置きで再試行する。
4. 下段は従来どおり GitHub の統合版から独立して採番する。②準備・検証、③公開は明示操作のみ。①だけで終了してもよい。
5. 以前のビルドにはビルド記録がないため、初回は①を実施する。現版のまま作り直す場合は据え置きを選ぶ。以後は据え置きと有効な記録で統合版のみの準備も可能。

## 実装
- GUI: バージョン選択、非同期ビルドログ表示、準備・公開ボタン制御。既存リリースパイプラインは変更しない。
- scripts/launch_release_build.py: APP_VERSION の限定置換、既存 BAT の起動、ビルド記録の生成・照合。
- _build_windows.bat: 既存ビルド工程を維持。GUI 経由のみ pause / Explorer 起動抑止。手動実行も記録する。終了待機はリダイレクトされた標準入力に依存しない方式にする。
- dist/.frb_launch_build.json: APP_VERSION ソースと EXE の SHA-256、および本体版を記録。ビルド開始・失敗時は以前の記録を無効にする。これはビルド結果の紐付けであり、EXE の内部版の独立検査や全ソース・全DLLの変更検出ではない。
- 統合版の GitHub 公開や Feed 更新は既存の承認経路を使用。ビルドだけで公開しない。

## 確認
- pytest: 16 PASS（模擬ビルドおよび静的GUI契約）。
- 最新 ZIP 内の実 app_version.py を複製し、0.9.14→0.9.15 の限定置換と記録照合を模擬ビルドで確認。
- Windows PowerShell 5.1、WinForms、PyInstaller 実ビルド、GitHub 実公開はこの環境では未実施。
- 既存 BAT と同じくビルド中に実行中の FRBLaunch.exe を停止する。
