# FRB Launch — Release 一覧が1件のときの DISCOVER 失敗修正

## 再現事象

```text
> DISCOVER
[{"isDraft":false,"tagName":"v0.9.8"}]
[ERROR] GitHub Release一覧の項目が不足しています。
```

GitHubから返された JSON の項目は揃っています。GUIの `ConvertFrom-Json` の受け取りで、Windows PowerShell 5.1 の配列展開状態によっては配列そのものを1行分として扱い、`PSObject.Properties` の検査が失敗する可能性がありました。

## 変更

- `release_FRBLaunch_GUI.ps1` に `Expand-ReleaseRows` / `Get-ReleaseVersions` を追加。
- JSON変換結果が空、単一オブジェクト、通常配列、入れ子の配列のどれでも、Releaseオブジェクト単位へ展開してから `isDraft` / `tagName` を判定。
- 既存の「Releaseが0件ならPreview Feedを採番基準にする」動作を維持。
- バージョン番号の選択、プレリリース公開、SHA256確認、公開時の人間承認を変更しない。
- 付属テストはネットワーク接続・GitHub公開なしで実行可能。

## 適用

1. GUIを閉じる。
2. ZIPを `F:\FRB_Apps\FRB_Launch` に上書き展開（変更ファイルだけ）。
3. GUIを再起動。`DISCOVER` の後、`GitHub latest v0.9.8` と表示されることを確認（実際の一覧が同じ場合）。
4. PowerShell 5.1で検証する場合は、Launchフォルダーで以下を実行。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_release_gui_discover_ps51_20261115.ps1
```

※Linux側ではPythonの静的テストのみ実行。Windows PowerShell 5.1実機検証は未実施です。
