# FRB Launch — Launch登録URLのダブルクリックを第3列 Browser Previewに統一

## 発端・再現条件

前回の第3列Browser Previewは、Files Listへ投影された **Chrome/Edge連携ブックマーク** のダブルクリックに限定されていた。**LaunchのJSONに直接登録したURL** は `runtime_catalog == browser_bookmarks` ではないため対象から外れ、従来のBrowserタブ起動経路に入った。

## 今回の仕様

- Files Listの **Launch登録URL** を左ダブルクリック → 既存の第3列 `Browser Preview` で表示する。
- Chrome/Edge連携ブックマークのダブルクリックも、これまでどおり第3列で表示する。
- プレビューは使い回し、別URLのダブルクリックで表示を切り替える。右上 `×` で閉じる。
- **Enterキー** と、Files List以外の操作は変えない。
- **単一の `Open` アクションでHTTP/HTTPSのURLを開く、現在有効なLaunch登録コマンドだけ** をプレビュー対象とする。`Run` や `Send`、複合アクション、アプリ、フォルダー、ファイル、`file:` / `javascript:` / `data:` 等は従来処理のまま。
- 登録済み項目は画面表示時のコピーを信用せず、**page_idとitem_idから現在の登録データを再照合** する。削除済み／無効化済み項目はプレビューしない。
- WebView設定が `mode=external` の場合はプレビューを作らず、元の外部ブラウザ動作を使う。
- **設定JSONの変更不要**。

## 変更対象

- `src/expanded_view.py`: Files List のダブルクリック判定を、Chrome/Edge連携ブックマークとLaunch登録URLへ分岐。アプリなどの非URLは除外。
- `src/app.py`: `preview_authored_launch_url` を追加。既存の `virtual_execution_row` と `bookmark_web_url` による再照合・安全確認を流用。
- `src/browser_preview_panel.py`: 前回のBrowser Previewパネル（**内容変更なし、適用漏れ防止のため同梱**）。
- `tests/test_browser_preview_authored_url_20261117.py`: 今回の機能追加テスト。

## テスト結果

- ブックマークプレビューと今回の追加テスト **12件 PASS**。
- 関連テスト（Files List /仮想Launchの投影 /アプリ等） **48件 PASS、2件環境依存失敗**。失敗2件は配布ZIPに個人設定 `config/frb_launch_data.json` が含まれず、テスト側が固定ファイルを参照しているため。このファイルを仮生成して成功扱いにはしていない。
- `python -m compileall` で対象ソース構文OK。
- **Windowsでの実際のPySide6/WebEngine GUI操作は未検証**。Chrome/Edgeブックマークで表示できたとの報告を受け、今回追加した登録URL経路はコード・非GUIテストで確認。

## 手動確認手順

1. Files ExpでLaunchのJSON登録フォルダーを選び、Files Listに登録URLを表示する。
2. URLを **ダブルクリック** → 右に第3列 `Browser Preview` が表示され、Filesワークスペースに留まる。
3. 別の登録URLをダブルクリック → 同じ第3列にページを切替。
4. `×` → 第3列のみ閉じ、2列の幅へ戻る。
5. Chrome連携ブックマークでも同様の操作を確認。
6. 参考：URLに対するEnterキーは従来の起動操作であることを確認。

## 適用方法

差分ZIPをLaunchのプロジェクトルートへ上書き展開する。`src/` `tests/` `docs/` の構成は保持。通常のソース起動では再起動、PyInstaller EXE版では再ビルドが必要。
