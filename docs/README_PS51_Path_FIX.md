# FRB Launch 0.9.6 — PowerShell 5.1 Path引数修正

## 現象
`release_FRBLaunch_GitHub.ps1 -Version 0.9.6 -PrepareOnly` で
`引数が空の文字列であるため、パラメーター 'Path' にバインドできません` が発生。

## 原因と修正
旧スクリプトの `param()` 内で `$LaunchSource = $PSScriptRoot` を既定値にしていたため、
PowerShell 5.1 のパラメーターバインド時に空文字列が入った可能性が高い。
その値が後続の `Join-Path` の `-Path` に渡されると、今回のエラーになる。

既定値を空にして、パラメーターバインド完了後に `$MyInvocation.MyCommand.Path` からスクリプトの配置場所を決定する。
フォルダーが不明／存在しない場合は分かりやすいエラーを出して停止する。
`-LaunchSource` に明示された値は尊重する。

## 適用手順
1. 差分ZIP内の `release_FRBLaunch_GitHub.ps1` を `F:\FRB_Apps\FRB_Launch` に上書きする。
2. Windows PowerShell 5.1で実行:

```powershell
cd F:\FRB_Apps\FRB_Launch
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\release_FRBLaunch_GitHub.ps1 `
  -Version 0.9.6 `
  -PrepareOnly
```

成功すれば `[ROOT] Launch source: F:\FRB_Apps\FRB_Launch` から進行する。
`-PrepareOnly` はGitHubへ公開せず、更新インストールも実行しない。

## 注記
- 既存の配布ZIPやGitHub Releaseは変更しない。
- Python側のリリース処理、Updater、バックアップ処理は今回変更しない。
- Linux環境で静的テストと元の回帰テストを実施。Windows PowerShell 5.1実機での再実行確認はユーザー側で必要。
