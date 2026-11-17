# FRB Launch — Launchバージョン v0.9.12／GitHubリンク追加

基準: `launch_app_20261116_235207.zip`

## 変更内容

1. `src/app_version.py`
   - `APP_VERSION` を `0.9.3` → `0.9.12` に変更。
   - Launch本体のバージョンを変更する場所はここ（single source of truth）。
   - GitHubのURLは既に `APP_REPOSITORY_URL` に定義済みなので再利用。
2. `src/update_information_dialog.py`
   - 設定メニューの **「バージョン情報...」で現在実際に開かれるダイアログ** にURLを追加。
   - 画面最下部（操作ボタンの直前）へクリック可能なリンクを表示。
   - リンク: https://github.com/tamasub/FRB-Launch
   - リンク表示分の高さを考慮してダイアログを少し拡張。
3. `tests/test_launch_version_0912_about_url_20261116.py`
   - APP_VERSIONとGitHub URL、設定メニューからの導線、リンク表示とクリック許可設定をQtなしで検証。

## 大事な区別

- `src/app_version.py` の `APP_VERSION` は **Launch本体** のバージョン。
- 「統合版」「Studio」「Updater」は別のバージョン管理。この差分では変更しない。
- `release-feed/preview/product_feed.json` 等の配布フィードも **変更しない**。配布公開操作で発行したリリース情報とは別物であり、未確認のアセットURLやハッシュ値を手動上書きしないため。
- 旧 `show_version_information()` の `APP_ABOUT_TEXT` には以前からGitHub URLが入っていたが、現在のメニューは `show_update_information()` → `UpdateInformationDialog` を呼ぶため、表示されていなかった。

## 適用方法

差分ZIPをLaunchプロジェクトルートへフォルダー構成のまま上書き展開する。

## 確認

```bat
python -m pytest -q tests/test_launch_version_0912_about_url_20261116.py
```

Windows実機で「歯車 → バージョン情報...」を開き、`Launch: 0.9.12`、画面下部のGitHubリンクが表示され、クリックでブラウザーが開くことを確認。

※PySide6 GUIのWindows実機でのクリック操作は、この環境では未確認。
