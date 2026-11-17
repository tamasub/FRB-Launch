# FRB Launch 不足モジュール復旧 / パス引数不具合修正版 (2026-11-17)

## 修正内容
以前のBATは `-LaunchRoot "%~dp0"` を付けてPowerShellを起動していました。
`%~dp0` の末尾バックスラッシュと引用符の解釈により、`GetFullPath` に無効な文字を含むパスが渡る可能性がありました。
修正版では **パス引数を完全に撤廃**し、PS1自身の配置場所を `$PSScriptRoot` から取得します。

## 実行手順
1. Launchを終了する。
2. **このZIP全体**を `F:\FRB_Apps\FRB_Launch` に展開する。
   - `Restore_Missing_Launch_Modules.bat` がLaunch直下にある状態にする。
   - 以前の同名 `.bat` / `.ps1` は修正版で上書きする。
   - 同梱の `restore_payload` は復旧元データであり、Launchの `src` を直接上書きしない。
3. `Restore_Missing_Launch_Modules.bat` をダブルクリックする。
4. `PASS` が出たらLaunchを通常の方法で起動する。

## 保護条件
- 復旧スクリプトは **存在しないPythonファイルだけ** を `src` に追加します。
- `src` にすでにあるファイルを上書きせず、そのSHA-256が変わらないことを検証します。
- JSON、設定、その他のデータファイルには触れません。
- `remote_confirmation.py` と `dialog_button_selection.py` も同梱済みです。
- 元ZIPは `launch_app_20261117_135958.zip` です。以降に新規追加されたモジュールが欠けている場合、それらまで補えるとは限りません。

## 補足
Windows実機のPowerShell実行は、この環境では未確認です。
実行後に別の `ModuleNotFoundError` が出た場合は、続きのエラーを確認してください。
