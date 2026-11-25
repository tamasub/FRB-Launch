# 配布用標準設定とアプリ連携オプション — 2026-11-25

## 目的・制約

- 開発環境で使用する個人設定は変更しない。配布時に個人設定を混入させない。
- `git_commit_options.json` と `file_index_options.json` の配布正本は `defaults/` とする。Portable / Update ZIP の双方で `defaults/` および実行時の `config/` に同じ正本を収録する。
- 標準設定が欠落・JSON不正・対象リストが空配列ではない場合は配布処理を失敗させる。開発用 `config/` やビルド済み `dist/` 内の同名設定へのフォールバックは禁止。
- Gitの登録リポジトリとファイル索引の指定フォルダーは空配列。索引方式は registered、最大並列数は2。その他の既存標準値は維持。
- オプション設定のアプリ連携タブで Obsidian / Visual Studio Code / サクラエディタ の埋め込み有無を独立して設定する。無効時は従来の外部起動経路を使用する。Studio の埋め込みフラグは非公開のまま維持する。

## 保存先と移行

- System: `config/app_embedding_options.json`。3項目の標準値は true。
- User: `%LOCALAPPDATA%/FRBLaunch/UserConfig/app_embedding_options.json`。初回オプション画面起動時、既存の `state.ini` の値を引き継ぐ。既存のUser JSONがあれば上書きしない。旧INIも変更しない。旧環境で未設定の項目は従来のOFF（VSCode/Sakuraの試験用環境変数が明示されている場合はその値）を引き継ぐ。
- 3項目の実行時読み込みはUser JSONの明示値を優先。User JSONがある場合、未指定キーはSystem値を参照する（Generic Editorの疎な上書きに対応）。User JSONがない場合は従来のINIに戻る。明示された不正値はOFF。Studioは引き続きINIのみ。
- 既存のStudio Family Generic Editorを利用し、Launch側のViewDefと登録定義を追加する。アプリのホストフラグは3つの真偽値だけを起動時に読み取り、プロセス中に固定する。Nodeの新規起動や毎操作時の再読込を増やさず、編集中のウィンドウのホスト方式が突然変わらないようにする。
- 旧配布版のインストール先 `config/file_index_options.json` を直接編集しており、UserConfigに移行していない場合は、更新前にバックアップすること。今回の変更は旧System設定を自動でUserへ移行するものではない。既存UserConfigは従来のUpdater保護対象のまま。

## 適用と確認

1. Launchを終了し、差分ZIPをLaunchソースルートに上書き展開。
2. `_build_windows.bat` で再ビルド。
3. オプション設定 → アプリ連携 → 3項目が表示され、現在のINI設定が引き継がれていることを確認。
4. 1項目ずつ無効にして保存、Launch再起動後に対象ファイルを開く。内部埋め込みではなく既存外部経路が利用されることを確認。他アプリへの影響がないことを確認。
5. 必要なら有効に戻し再起動して元の埋め込み動作を確認。
6. 配布ZIPを作り、`config/` と `defaults/` の2つの対象JSONが一致し、個人パスを含まず、索引標準並列数が2であることを確認。

## 検証

- Python 3.13/Linuxで関連テスト141 PASS / 1 FAIL / 1 SKIP。新規契約テスト15件は全件PASS（テストファイル内のパラメータ展開込み）。
- 既存FAILは添付ZIPのGUIリリーススクリプト名が `_★release_FRBLaunch_GUI.ps1` で、テストは `_release_FRBLaunch_GUI.ps1` を参照する不一致。今回の範囲外。
- SKIPは隣接Studioソースが存在しないためNode Composer実連携テストを実行できないもの。
- 共通ダイアログおよびコンテキストメニュー制約チェックPASS。
- Windows実機・実際のStudio Generic Editorでの新規タブ表示・保存・外部起動は未検証。実物の配布バイナリは生成していない（模擬ランタイムから実際のZIP生成と検証を実施）。
- Launchバージョン、Studio本体、Updater本体、個人設定ファイル、max_scan_workersのオプションUIは変更対象外。
