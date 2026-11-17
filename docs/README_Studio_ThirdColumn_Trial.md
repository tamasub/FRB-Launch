# FRB Launch — 第3列 FRB Studio 収容 実験版（2026-11-17）

## 目的

Files Listの **.md**、または既存StudioのViewDefを解決できる **.json** をダブルクリックしたとき、従来のC# FRB Studio / NativeShellを **第3列に収容** する。

**保存は既存StudioのWebView2 → C# NativeShellの保存処理に委譲**。Python側にMarkdown/JSONの書込み処理を増やしていない。C#からPythonへの移植、Studioの再コンパイル、ユーザー設定JSON変更は不要。

## 動作と範囲

- Files Listの`.md`をダブルクリック → 第3列で既存Markdown Studioを表示する試み
- `view_def`が解決できる`.json`をダブルクリック → 第3列で既存JSON Studioを表示する試み
- `Enter`やその他のファイルタイプ、登録されたアクションは従来どおり
- URLは従来のBrowser Preview（第3列）を使用し、Studioとは排他的に表示
- Studioの保存ボタン／保存機能は今までのC# NativeShellが担当
- 第3列の「×」は**Studioを終了せず通常ウィンドウに戻す**（未保存データ保護）
- 別の.md/.jsonへ切り替えた場合も、それまでのStudioは通常ウィンドウとして残る。Studioを閉じる場合は**保存後にStudio側で終了**すること
- Launchを明示的に終了する際も、Studioを通常ウィンドウへ戻す
- Windows専用（Win32 `SetParent`を使うネイティブウィンドウ収容の実験）

## 導入方法

1. 必ず元の`launch_app_20261117_125435.zip`と、現在使っているLaunchフォルダーをバックアップ。
2. この差分ZIPの`src/`および`tests/`を、Launchのプロジェクトルートへ展開して上書き。
3. 既存の`NativeShell/_publish/FRBStudio.NativeShell.exe`がこれまでの`.md`や管理JSONのダブルクリックで動く状態であることを確認。
4. 開発版なら`_run_windows.bat`などからLaunchを再起動。**EXE版はLaunchの再ビルドが必要**。Studioの再ビルドは不要。

## Windowsでの手動確認（重要）

1. 既存の通常Studioでテスト対象のバックアップを作る。
2. Files Listでコピーした`sample.md`をダブルクリック。第3列にStudioが現れるか確認。
3. 一文追記→Studio標準の保存操作→ファイルを別ツールで再読込し追記が保存されているか確認。
4. Files ListでViewDefをもつテストJSONをダブルクリック。セル編集→Studio標準の保存→再読込で永続化を確認。
5. Studio内をクリックしてもLaunchが消えないこと、スクロール、文字入力、保存ダイアログ等が扱えることを確認。
6. 第3列「×」を押すとStudioが別ウィンドウへ戻ることを確認。未保存編集が失われないことも確認。
7. Chrome連携やLaunch登録URLのダブルクリックは従来どおりBrowser Previewが表示されることを確認。
8. 通常のEnter、非管理JSON、アプリ起動等が従来どおりであることを確認。

## 制約／リスク

- **Windows上のQt + WinForms + WebView2の実画面、保存はこの実行環境から検証できていません。** つまり機能成立を保証した完成版ではありません。
- 異なるDPI設定、WinFormsのハンドル再作成、フォーカス、ポップアップや保存ダイアログの表示位置などで埋め込みが成立しない可能性があります。
- Studio自身は独立プロセスです。切替／×で旧Studioが通常ウィンドウに残るので、同一ファイルを複数Studioで同時編集しないでください。
- 収容失敗時は、起動済みStudioの通常ウィンドウを使用してください。Studioのデータを書き換えるリカバリー処理は行いません。
- 現段階はまず「本物のStudioを第3列で使い、保存できるか」をWindowsで確かめるための実験。長期的には専用の埋め込みホスト／APIブリッジなど、より安定した構造も検討できます。

## 修正ファイル

- `src/expanded_view.py` — Files Listダブルクリックの割当、第3列の共存
- `src/app.py` — Launch終了時のStudio切り離し
- `src/desktop_double_click.py` — 収容済み外部プロセスのクリックはLaunch内部として扱う
- `src/studio_preview_route.py` — `.md`／Studio管理`.json`の適格性と起動引数
- `src/studio_preview_panel.py` — 第3列UI、起動・表示・切り離し
- `src/studio_win32_host.py` — Windowsの親子ウィンドウ切替（元のWindowスタイル復元あり）
- `tests/test_studio_preview_third_column_20261117.py` — ルーティング等のテスト

関連のURL Preview・新規Studioルーティングテストは22件PASS。Windows実機テストは未実施。
