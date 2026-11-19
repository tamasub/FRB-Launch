# FRB Launch — サクラ表示中のURLダブルクリック修正

基準: `launch_app_20261119_183235.zip`

## 症状

サクラエディタが第3列に表示されているとき、Files ListでURLをダブルクリックすると「サクラエディタを収容中」ダイアログが繰り返され、最終的にChromeを勝手に起動する。

## 原因

`ExpandedLauncherView.show_browser_preview()` が第3列の使用中を理由に `False` を返すと、Files List 側が「未処理」として通常の `activate()` 経路へ進めてしまう。この経路で外部ブラウザを起動していた。また、同期（モーダル）ダイアログが連続入力を妨げていた。

## 修正

`src/expanded_view.py` の URL プレビュー入口で、サクラの第3列収容中を先に検出する。

- HTTP(S) URLダブルクリックを「開かなかったが処理済み」として消費する
- Launchの非モーダルな下部通知（`info_notice`）で「外に出す」または「×」を案内する
- Chrome等への暗黙のフォールバックをしない
- サクラのウィンドウ・タブ・保存内容には手を触れない
- サクラの収容解除後は従来通りBrowserプレビューで開ける
- Obsidian/VS Codeの収容方式、`state.ini`、ビルドバッチは変更しない

## 差分ZIP内

- `src/expanded_view.py` — 修正本体
- `tests/test_sakura_url_blocked_no_chrome_20261119.py` — 新規回帰テスト
- 本README

## 適用 / 実機検証

1. FRB Launchを完全終了する。
2. 基準版以降のコードへ本ZIPをフォルダー構造ごと上書き展開する。
3. `_run_windows_Try_Sakura_Overlay.bat` から起動する。
4. `001.txt → 002.txt → 003.txt → 001.txt → 002.txt` のテキスト回帰テストを実施する。
5. サクラを収容したまま、Files ListのURLをダブルクリックする。
   - 期待: ダイアログのループなし、Chrome起動なし、下部に非モーダル案内。
   - サクラは第3列に残り、本文・タブ・未保存編集内容も保持される。
6. 第3列ヘッダーの「外に出す」を押してからURLを再度ダブルクリックする。
   - 期待: URLがLaunch第3列のBrowserに表示される。
7. サクラ収容中に右上「×」を押せるかも確認する（元の安全な閉じ方を維持）。

## 自動検証

- 本件関連テスト: 38 PASS / 3 FAIL。
- FAIL 3件は未修正の元ZIPでも同じ（既存の古い実装前提のテスト）。今回の差分による追加失敗は観測していない。
- Python構文コンパイル PASS。
- Windows実機でのGUI操作は未確認。修正の有効性は実機で最終判定する。
