# FRB Launch: Browser本体の第3列統合／Launch内最大化（2026-11-19）

## 適用元

`launch_app_20261119_110920.zip`（提供された11:09版）に対する**相対パス差分**。フルソースではない。Launch停止後、元の作業フォルダーをバックアップして差分をルートへ上書きする。

## 今回の確定仕様

1. 「Files／Browser」切替タブの**表示領域ごと非表示**にし、縦44pxを取り戻す。Files ExpとFiles Listは常時左側。パンくず／三本線はFiles側ヘッダーのまま。
2. 初回の第3列Browser幅は約50%（旧小型Browser Previewの幅設定とは独立）。URLダブルクリック・既存のBrowser URL起動経路・RemoteのBrowser起動で、**本来の `LaunchWebView`** を第3列へ表示。旧 `BrowserPreviewPanel` はそのホストに変更。タブ／URL／戻る／進む／更新／ダウンロード／URLお気に入りを持つ。旧単純な `QWebEngineView` は廃止。
3. Browser内の横一列ブックマークバーは非表示。ブックマークデータは消さない。Exp/List/Keyborderの操作は残す。
4. Browser、Studio（Obsidianなども同じホスト）両方の第3列ヘッダーに「最大化／戻す」ボタン。**Launch本体の大きさは変えず**、Exp約190px、List約190px（Remote1.5列時はExp側約386px）を残し、余剰幅を第3列へ配分。
5. 最大化解除で「最大化直前の3列幅」を復元。最大化したままLaunchサイズ変更時も残余幅を第3列へ再配分。最大化中の一時幅はQSettingsへ永続化しない。
6. 第3列の×は従来どおり**第3列を隠す**。Browserはタブ・履歴保持。Studio／Obsidianは既存の終了・デスクトップへ戻す処理を変更しない。
7. ぐりぐりボタンは**ExpとListの間の `files_splitter.handle(1)`** にのみ追従。開閉・幅変更・最大化／復元・Launch自体のサイズ変更後に再配置する。
8. Studio↔Browserの表示切替時、最大化中なら最大化状態を引き継ぐ。アプリ側の収容可否・未保存対策は従来どおり。

## 実装ファイル

- `src/expanded_view.py`: Tab領域廃止、Browser本体を第3列へ、表示切替、共通最大化、再配置
- `src/browser_preview_panel.py`: 旧小型PreviewからLaunchWebViewを含むBrowser本体ホストへ置換（既存名称は互換維持）
- `src/studio_preview_panel.py`: Studio／外部エディタヘッダーに最大化ボタン
- `src/browser_nav_icons.py`: 最大化／復元のベクターアイコン
- `src/third_column_maximize.py`: Qtに依存しない列幅演算（新規）
- `src/app.py`: 一部Remote操作およびブラウザ画面リサイズ検知を、第3列表示判定へ対応
- `tests/test_browser_third_column_workspace_20261119.py`: 今回の専用検証（新規）

## テスト／未検証

- `python -m py_compile`：対象PythonファイルでPASS。
- 新規専用テスト：**14 PASS**（列幅、4列の隠し枠、最大化／復元、Launchサイズ変更、URL新タブ経路等）。
- 関連テスト部分実行：**67 PASS、2 FAIL**。2件は旧「簡易Browser Preview」仕様を固定しているテスト（旧Previewの直接QWebEngineView描画・旧スタブAPI）で、新仕様に更新が必要。
- Browser/WebView/Studio関連の広めの回帰：変更前 **30 FAIL／185 PASS／9 SKIP**、変更後 **41 FAIL／186 PASS／9 SKIP**。増えた失敗11件は、旧Browserタブ・旧Previewへの直接呼出・旧Remote状態など旧レイアウト前提のテストが中心。**新仕様用テストへの移行が未完了**。古いテストを黙って修正・削除してはいない。
- Linux環境にはPySide6がないため、**Windows 11でのQt実描画・WebEngine・クリック・Native Studioドッキングは未検証**。UIの実機確認が必要。

## Windows実機スモーク（推奨順）

1. Launch起動直後、Files／Browser切替タブがなく、Exp＋Listが全幅を使う。ぐりぐりがExp/Listの境界にある。
2. ListでURLをダブルクリック → 第3列に**全機能付きBrowser**。横並びブックマークは見えない。Webタブ+、URL入力、戻る、進む、再読込、ダウンロードを確認。
3. 第3列「最大化」→Exp/Listを最小にして残りがBrowser。ぐりぐりはExp/List境界。
4. 「元へ戻す」→前の3列幅へ復帰。×→Filesが全幅。再度URLで開いた場合、Browserの既存タブが残っている。
5. JSONをダブルクリック → Studioが第3列へ。Studio側でも最大化／復帰を実行。外出し、×、Launch終了時の既存ルールを確認。
6. ObsidianでMarkdownを開く経路は**前版の本体収容動作を維持**。今回の改修でObsidian本体識別・起動処理は変更していないため、前から残る問題は残課題。
7. 最後に、最大化状態のまま**Launchのウィンドウ幅を変更**し、ぐりぐり位置・各列の最小幅・復元後の位置を確認。

## 保留／注意

- `src/expanded_view.py` 内に旧ブラウザーのレイアウト互換関数や、参照用の非表示タブオブジェクトを残している。**視覚的なタブ操作は廃止**だが、全面削除は関係先の操作影響を広げるため今回実施していない。
- 古いBrowser Preview向けのテスト、Browser専用レイアウトを想定するRemoteテストは仕様変更に合わせて後日更新が必要。
- 第3列を広く使うための最小値はQtウィジェット自身のminimumWidthや画面幅によって最終的に調整される。
- 不具合が出た場合は、上書き前の`launch_app_20261119_110920.zip`へ戻す。Studio本体コード・データJSONは変更していない。
