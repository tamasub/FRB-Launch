# FRB Launch: URL表示復旧 + Studio版表示の統合 (2026-11-17)

## 原因

11/17 の Studioバージョン表示改修で `src/update_information_dialog.py` の11/16版 GitHub URL 表示コードを上書きしていた。

## 修正

- `src/update_information_dialog.py`：`APP_REPOSITORY_URL` を読み込み、Studioバージョン行を残したまま GitHubリンクを復元。リンクはボタンより上に表示し、外部ブラウザで開ける設定を維持。ダイアログ高さを320に戻す。
- `src/app_version.py`：11/16の公開版に合わせて APP_VERSION=`0.9.12` を復元。
- `tests/test_launch_about_studio_version_combined_20261117.py`：両機能の共存、リンクの外部オープン設定、Studio版の参照を退行テスト。

## 適用

**11/17のCSV replace_groups / Studioバージョン表示差分を適用済みのLaunch** に、このZIPをLaunchのルートへフォルダ階層ごと上書きしてください。Launchを終了してから適用してください。

このZIPには `defs/launch`、CSVの取り込み処理、`src/studio_version.py` は含みません。**以前の差分を再適用する必要はありません。**

## 検証

- 自動テスト: 既存 `test_studio_version_info_20261117.py` と新規 `test_launch_about_studio_version_combined_20261117.py`
- 手動確認が必要: Windows 11で 設定 → バージョン情報 を開き、Studio版表示とGitHub URLの表示・クリック遷移を確認。
