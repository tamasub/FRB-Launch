# FRB Launch 0.9.8 — 新規インストールで最新版を発見できるようにする修正

## 目的

別端末の既存FRB Launch環境は不具合再現用としてそのまま保存します。`-ConfigureTestInstall` は実行しません。

`v0.9.7` までの配布用 `defs/update/update_sources.json` には更新元URLが空で入っていたため、新しい端末へインストールすると「Updater／製品の更新先URLが未設定です」と表示されました。

## 修正内容

- `defs/update/update_sources.json` : GitHubの `main/release-feed/preview/` にある製品・Updaterの**固定**HTTPS Feed URLを同梱。バージョン `v0.9.8` をURLに埋め込まない。
- `scripts/release_github_pipeline.py` : 配布準備の開始時にソースのURLを検査。検証・公開前に**portable.zipとupdate.zip両方の実際の格納JSON**を検査。空欄・旧固定版URL・ローカルURLなどは公開できない。
- `tests/test_release_fresh_install_feeds_098.py` : URL不正、ZIP不正、新規UserConfigの初期移行、既存UserConfig非変更をテスト。

**既存のUserConfig設定や検証端末には一切手を加えません。** 旧版リリースのGitHubアセットも変更しません。

## Windowsでの適用と検証

1. 差分ZIPを `F:\FRB_Apps\FRB_Launch` へ展開（元の `defs` / `scripts` / `tests` の階層を維持）。
2. 今回は **Launch本体の `src` は修正していません。** すでにビルド済みのEXEが最新なら、`_build_windows.bat` の再実行は不要。
3. `FRB_Release_Manager.ps1` を今まで成功した方法で起動。GitHub最新版 `0.9.7` から次版 `0.9.8` が提案されることを確認。
4. `① 準備・検証（公開なし）` を押す。ログに次が表示されることを確認：

   ```text
   [OK] Fresh-install defaults point to fixed Preview feeds
   [OK] Portable and update ZIPs both ship the correct Preview feed URLs
   ```

5. 内容・SHA・公開内容が問題なければ、**GUIの公開確認を承認**してGitHubに `v0.9.8` を公開。
6. **別端末**で、GitHubの `FRBLaunch_0.9.8_portable.zip` を新規フォルダーへ展開。古い0.9.7フォルダーは変更せず保存。`Start_FRB_Launch.bat` または `FRBLaunch.exe` を起動。
7. バージョン情報の「最新版を確認」で次を検証：
   - 統合版 `0.9.8`
   - 最新版 `0.9.8` / Updater `0.9.8`
   - **「更新先URLが未設定です」が出ない**
   - 最新版なので、更新ボタンが無効なのは正常
8. 将来 `0.9.9` を公開したときに、**0.9.8の設定を触らずに** 新版情報アイコンと更新ボタンが表示されるか検証。

`-ConfigureTestInstall` は使いません。SmartScreen警告はコード署名がないアプリで起こり得ます。警告が出た場合はダウンロード元と配布SHA-256を確認し、Windowsの保護を無効化する操作はしないでください。

## テスト実施状況

ローカル環境のPythonによる関連テスト39件PASS。Windowsでのリリース操作・新規インストール実機確認は未実施です。
