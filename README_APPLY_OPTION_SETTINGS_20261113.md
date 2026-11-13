# FRB Launch — オプション設定 / Generic Editor 実験差分 v0.1

適用先: `F:\FRB_Apps\FRB_Launch` (Launchの独立リポジトリのルート)

## 前提
1. 先に `FRB_Studio` へStudio側の差分ZIPを展開する。
2. Node.jsがPATHで実行可能か、`runtime/node/node.exe` を同梱する。
3. LaunchをPythonソースから起動する場合は `_run_windows.bat`、EXEを使う場合は `_build_windows.bat` で再ビルド。

## 起動
Launchの設定メニューに、既存「メニュー設定 (FRB Studio)」を残したまま、その直下へ `オプション設定...` が追加されます。
新画面にはブラウザーとファイル検索の**2つだけ**を表示します。
内部設定4種類などは公開しません。ユーザーに許可された設定のみViewDefで表示します。

## SystemとUserの分離
- System: `FRB_Launch/config/*.json`（元の設定ファイルは今回そのまま）
- User: `%LOCALAPPDATA%\FRBLaunch\UserConfig\*.json`（**保存した時に初めて作成**）
- 合成結果: `%LOCALAPPDATA%\FRBLaunch\EffectiveOptions\*.json`（削除可能な一時ファイル）
- 保存後にLaunchを再起動すると、Node合成Coreが標準値＋User保存値を合成して読み込みます。
- バックアップスクリプトは新しいUserConfigを対象に追加。

## 配布用Node.exe
公式Node.js Windows版ZIPのnode.exeとLICENSEを指定して、例えばPowerShellで実行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Prepare-OptionNodeRuntime.ps1 `
  -NodeExecutable 'C:\trusted-node\node.exe' `
  -NodeLicenseFile 'C:\trusted-node\LICENSE'
```

その後、Launch ZIP配布時に `runtime/node/` と、Studio側の `tools/option_settings/` と `defs/launch/options/` を必ず含める。

## 動作確認
- Node新規テスト8/8 PASS
- Launch関連テスト19/19 PASS
- 既存リモート操作に関する3件のレガシー期待値不一致は凍結版の時点で存在（本差分とは別）

## 未完了／今回の検証範囲
- Windows GUIの実機テストはこの実行環境では未実施。
- Studio本体へのEditor実装の一本化は次工程（旧詳細Editorは現存）。
- 既存設定JSONに含まれる過去の利用者固有値を、将来の製品標準値からUser領域へ移すデータ移行は未実施。
- 新設定画面は2カテゴリのみ（Git、ログ、展開表示、コンテキストメニューは公開していません）。
