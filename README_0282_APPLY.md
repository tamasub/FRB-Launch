# FRB Launch 0282 — 旧Studioパス依存解消

* 現在の `F:\FRB_Apps\FRB_Launch` に差分ZIPを上書き展開します。
* `config/frb_launch_data.json` は同梱していないため、設定データを上書きしません。
* Launch exeで利用している場合、Launchフォルダーの `_build_windows.bat` を実行して再ビルドしてください。
* 新Studioで `NativeShell\_publish\FRBStudio.NativeShell.exe` がなければ、先にStudioの `cmd_compile_NativeShell.bat` を実行してください。
* 旧Studioのフォルダー名は元に戻す必要ありません。
* 実機テストはこれからです。詳細は docs/FRBLaunch_0282_FRBApps_SiblingStudio_AutoDiscovery_20261112.md へ。
