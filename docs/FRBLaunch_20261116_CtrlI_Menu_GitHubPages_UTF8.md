# FRB Launch 修正記録 — Ctrl+I と GitHub Pages 文字化け

基準: `launch_app_20261116_220209.zip`（2026-11-16）

## 1. Ctrl+I

- 従来: `ExpandedLauncherView.keyboard_files_shortcuts()` から `launcher.open_option_settings()` を直接呼び、設定ダイアログを開いていた。
- 今回: `launcher.open_theme_menu()` を呼ぶ。ヘッダーの歯車ボタン `.clicked.connect(self.open_theme_menu)` と同一経路。
- Files/Browser拡張画面でキーボードから歯車メニューを表示する。メニュー項目の変更は行わない。

## 2. GitHub Pages の文字化け

今回の添付ZIPには `docs/FRB_Launch.htm` と `docs/FRB_Launch.files/` が存在する。

- ZIP内のトップHTMLは実データUTF-8なのにHTMLの宣言が `charset=shift_jis` だった。
- Excel出力の `sheet001.htm` / `sheet002.htm` / `tabstrip.htm` はCP932（WindowsのShift_JIS系）だった。
- `stylesheet.css` にもCP932の日本語フォント名が入っていた。

次の5ファイルを実バイトごとUTF-8へ統一した。

- `docs/FRB_Launch.htm`
- `docs/FRB_Launch.files/sheet001.htm`
- `docs/FRB_Launch.files/sheet002.htm`
- `docs/FRB_Launch.files/tabstrip.htm`
- `docs/FRB_Launch.files/stylesheet.css`

HTMLの `charset=utf-8` とCSS冒頭の `@charset "UTF-8";` を一致させた。関連XMLや画像は変更していない。

### GitHub Pagesへ反映する方法

1. 差分ZIPをFRB Launchプロジェクトのルートに上書き展開する。
2. リポジトリで `docs/FRB_Launch.htm` と `docs/FRB_Launch.files/` の変更をGitにコミット・プッシュする。
3. GitHub Pagesのデプロイ後、該当URLをブラウザーで強制更新（Ctrl+Shift+R）する。
4. ページの「機能マップ」など日本語見出しと表の内容を確認する。

**注意**: ルートHTMLだけをGitHubへ上げても不十分。表本体の `sheet001.htm` を含む5ファイルをまとめて更新する必要がある。

### 次にExcelからHTMLを再出力した場合

ExcelがCP932を再生成した場合は、**再出力後・Git push前**に以下を実行する。

```powershell
python scripts/normalize_frb_launch_excel_html.py
```

すでにUTF-8のファイルでも再実行してよい。`docs`内の必要な5ファイルのみ変換する。

## 3. 動作検証

- 修正対象のPython構文チェックPASS。
- Ctrl+I・Tab・Homeと関連メニュー、HTML UTF-8契約を中心に pytest 30件PASS。
- Excelシートの日本語、関連ファイル参照、UTF-8の再実行安全性を自動検査。
- 実Windows GUIでのクリック・キーボード操作およびGitHub Pagesへの実デプロイは未実施。

現行ZIPには他の旧テスト期待値と現行実装がずれるケースがあるが、本差分では修正対象外としている。
