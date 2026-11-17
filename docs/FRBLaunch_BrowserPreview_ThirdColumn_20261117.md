# FRB Launch — 第3列 Browser Preview 試験実装 (2026-11-17)

## 仕様 / 変更点

- Files ワークスペースの **Files List** に投影された **Chrome/Edge のブックマーク URL（HTTP/HTTPS）** をダブルクリックすると、右側に第3列 `Browser Preview` が出現し、WebEngine でページをレンダリングする。
- 第3列右上の `×` で閉じ、開く前の Files 2列の幅を復元する。ブックマーク選択・フォルダー・履歴データは変更しない。
- プレビュー表示中に別のブックマークをダブルクリックすると、**同じ第3列**でURLを切り替える（新たな列/タブは作らない）。
- Files List での Enter、非ブックマークのダブルクリック、Browser ワークスペースの既存タブ操作は従来どおり。
- Remote の Files List 領域からのダブルクリックにも同じ第3列を適用。
- WebView設定が `mode=external` の場合は埋め込みプレビューを開かず、既存の外部ブラウザ動作を維持する。
- `file:`, `javascript:`, `data:` 等は拒否。最新のランタイム・ブックマークを再照合し、古い行のリンクは開かない。
- WebEngine 初期化はダブルクリックまで遅延。既存の `LaunchWebView` が初期化済みなら同じ Launch 内の WebEngineプロファイルを利用する。それ以外は Qt のデフォルトWebEngineプロファイルを利用する。
- 埋め込みプレビューを閉じるとページ読み込みを停止し `about:blank` にする（他のBrowserタブは変更しない）。

## 変更ファイル

- `src/expanded_view.py` — Files 3列対応、ダブルクリックの分岐、表示/閉じる、幅復元、Remote連携用API。
- `src/app.py` — ブックマークIDの正当性再確認、Preview URLルート、Remote ダブルクリック分岐。
- `src/browser_preview_panel.py` — 新規：QWebEngineView利用の右側プレビューパネル。
- `tests/test_browser_preview_third_column_20261117.py` — Qt-independent 7件の確認。

## 確認事項と制約

- Linuxコンテナには PySide6 がないため、**実画面の表示/読み込みは未検証**。Python構文およびQt非依存のルーティング・ロジックテストは実施した。
- ログインの必要なサイトでは、Chrome/Edgeのログイン状態を引き継がない。Browser起動済みならLaunch内の既存WebEngineプロファイルを共有する。
- 現状は実験版としてページ表示＋閉じるだけ。タブ、URL編集欄、戻る/進む、ダウンロード制御、ポップアップ窓は後続検討対象。
- テスト手順：Files→Bookmarks→ブックマークフォルダー→URLダブルクリック→Preview表示→別URLダブルクリック→同じ第3列に表示→×→幅復元。あわせて Enter/外部ブラウザモード/非URLダブルクリックを確認。
