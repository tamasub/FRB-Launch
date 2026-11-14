# FRB Launch 進捗表示・Feed設定永続化 修正差分

## 現象
- 0.9.3への更新は正常完了したが、Updaterの完了画面で進捗バーが途中に残る。
- 更新すると `defs/update/update_sources.json` が配布物の空テンプレートに戻り、更新先URLが失われる。

## 対応
1. ネイティブWin32進捗UIを、マーキー用／数値用の独立した2つのコントロールに分離。完了時には数値用を表示し、100%に固定する。失敗時は0%に固定。
2. LaunchのFeed設定は `UserConfig/update_sources.json` を最優先。存在しない場合は従来の `defs/update/update_sources.json` を読み、両URLが設定済みならUserConfigへ移行する。
3. `UserConfig` はUpdaterの管理対象から除外された既存の保護領域。Updater本体の更新／ロールバック実装とJournal処理は変更しない。

## 注意・試験方法
- これらは**ソース修正**。現在の `FRBLaunch.exe`／`FRBUpdater_0.9.3.exe` を修正するものではない。
- 現在の0.9.3でURLが消えた状態は、まずテスト用Feedを再設定する必要がある。付属の `restore_093_test_feed_and_seed_userconfig.ps1` を使用する。
- 次の更新を実証する際は、修正ソースから **LaunchとUpdaterの両方**を再ビルドし、既存の配布物は上書きせず新規バージョン（例: 統合版0.9.4、Updater 0.9.4）を割り当てる。
- Launch側の新コードは新しいLaunch起動後から有効。次の更新時に古いLaunchから失われないよう、付属のPS1でUserConfigを先に作成する。
- `UserConfig/update_sources.json` が不正な場合、空設定へのサイレントフォールバックはしない（エラーにして発見可能にする）。
- 開発者のWindows実機でのUI表示・更新確認は未実施。ソーステストのみ。

## 元の0.9.3成功確認
画像上は `統合版: 0.9.3`, `Launch: 0.9.1`, `Studio: 0.9.0`。URL再取得失敗は更新パッケージによるSystem設定上書きで説明できる。
