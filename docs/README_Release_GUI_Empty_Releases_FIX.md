# FRB Launch Release Manager — GitHub Releases 0件対応

## 原因

GitHub Release を全削除した状態では `gh release list --json tagName,isDraft` が `[]` を返します。
旧GUIでは PowerShell 5.1 + StrictMode 下で空配列に混ざる `$null` 要素の `isDraft` プロパティを参照して失敗していました。

## 修正

- Release `[]` ならプロパティ参照で例外にせず、固定 Preview Feed を取得します。
- `main/release-feed/preview/product_feed.json` の `version` を過去の採番基準として使用します。
- 現在の Feed が v0.9.7 の場合、GUIは `Release 0件` と表示し、次版を `0.9.8` と提案します。
- Feedが取得できない場合はバージョンを推測せず、準備／公開を無効のまま停止します。
- 実際に GitHub Release がある場合の採番は従来のままです。
- 公開時の確認ダイアログ、配布準備、SHA-256検証、既存アセット保護は変更しません。

## 適用

1. GUIを終了。
2. ZIPを `F:\FRB_Apps\FRB_Launch` に上書き展開。
3. `release_FRBLaunch_GUI.ps1` をいつものPowerShellから起動。
4. `DISCOVER []` の後、Preview Feed取得へ進み、0.9.8が自動提案されることを確認。

Launch本体の `_build_windows.bat` は不要。検証端末の設定も変更しません。

**注意**：Releaseを削除してもPreview Feedは残っている場合があります。その場合は古い配布先を指すため、公開が完了するまで既存端末での更新テストは行わないでください。

## テスト範囲

Linux上の静的・契約テストまで。Windows PowerShell 5.1でのGUI実行は未確認です。
