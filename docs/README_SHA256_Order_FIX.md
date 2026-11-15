# FRB Launch 0.9.5 GitHub配布準備 — SHA-256照合順序修正

## 原因
`scripts/build_portable_distribution.py` が出力する `SHA256_0.9.5.txt` は `portable.zip → update.zip → updater.exe` の順。一方、`scripts/prepare_github_release_095.py` は `update.zip → portable.zip → updater.exe` の順にテキスト全体を比較していたため、内容が一致していても停止していた。

## 今回の修正
- SHA256の照合を、行順ではなく **ファイル名とSHA-256の対応** で行う。
- 実際のSHA-256不一致、記載漏れ、重複、未知のファイル名、書式異常では停止する。
- 既存の `SHA256_0.9.5.txt` を書き換えない。既存ZIPやUpdater EXEも変更しない。
- Windows CRLF改行も許容。

## 適用と再実行（Windows PowerShell 5.1）
1. このZIPの `scripts/prepare_github_release_095.py` を `F:\FRB_Apps\FRB_Launch\scripts\prepare_github_release_095.py` に上書きする。`tests/` は回帰テスト用（任意）。
2. 以前と同じコマンドを再実行する。

```powershell
cd F:\FRB_Apps\FRB_Launch
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBLaunch_0.9.5_GitHub_test.ps1
```

`[INFO] Reuse existing 0.9.5 ZIPs without overwriting.` と `[OK] SHA256 inventory agrees with all 3 staged artifacts (order-independent)`、`[SAFE] Prepared. Nothing uploaded or installed.` が出れば配布準備段階は完了。

**注意**：`SHA256_0.9.5.txt` を削除したり無条件に再生成したりしない。ハッシュ不一致が続く場合はログを保存し、配布を停止する。GitHubへのアップロードは `-PublishRelease` を指定するまでは行われない。

## 確認済み
Python構文チェックPASS、関連ユニットテスト10件PASS（順序違い・Windows改行・実不一致・重複・余剰エントリを含む）。Windows実機では未実行。
