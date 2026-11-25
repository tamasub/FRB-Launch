# Commander 前面制御・コマンドコピー（2026-11-25）

## 文脈・責務
- Commanderが常時最前面、確認応答がLauncher所有だったため、確認応答がCommanderの後ろに隠れることがあった。
- Commanderの責務はViewDefから引数を生成・発行すること。PS1固有のNode等の依存関係には関与しない。

## 変更
- Commander本体および候補Toolの独自のWindowStaysOnTopHintを削除。LauncherとのQt親子関係は維持。ネイティブ所有ウィンドウとしての前面関係は残る。
- 共通確認・入力・通知に呼び出し元owner指定を用意。Commander実行・終了確認でowner=self。共通アダプターが親ウィンドウの前面属性を継承し、既存のNonModal/Guard/No初期選択/Remote操作を維持する。確認応答中の再実行・Commander閉じ操作を抑止。
- 実行ボタン左に「コマンドコピー」。選択完了時のみ有効。実行と同じCommanderCommand（program、argv、working_directory）を生成する。コピーはPowerShell 5.1で貼り付け実行できるStart-Process形式（Windows引数列の引用、作業ディレクトリ指定、-Wait）。コピー時に確認応答・実行は行わない。入力不正ならクリップボードを変更しない。環境変数等は貼り付け先の環境に依存する。
- ViewDef仕様、PS1、Node探索、設定JSONは変更しない。

## Windows受入
1. Commanderを開いて候補表示、Keyboard Ex、IME選択を確認。Launchの前面制御に従い候補が隠れないこと。
2. 選択完了後にコピー、PowerShellへ貼り付けて文字列確認。コピー時にPS1を実行しないこと。日本語・空白・引用符を含む入力で確認。
3. 実行ボタンから確認がCommanderより前に出ること。No、Yes、ホイール、Remote、直接ボタン操作を確認。実行中に閉じる確認でも同様。
4. コピーしたコマンドと実行ボタンで、対象PS1、引数、作業ディレクトリが一致すること。実際に実行する場合は副作用を確認してから行う。
5. 他の共通確認・入力・通知、Remoteの表示/非表示も確認。

LinuxではWindowsネイティブZ-order、PowerShell 5.1実行、クリップボードGUIを実機検証できない。Qtがない環境ではQt受入テストはskipとなる。

## 検証結果
- 対象回帰テスト: 変更前75 PASS / 2 FAIL / 2 SKIP、変更後81 PASS / 2 FAIL / 3 SKIP。新規6 PASS / 1 SKIP。
- 既存FAIL: `test_no_focus_style_is_applied_to_actual_buttons_not_only_remote_label`、`test_background_list_wheel_selects_confirmation_and_consumes_event`。変更前にも同じ2件が失敗。
- Python構文検査・共通ダイアログ契約・コンテキストメニュー契約: PASS。
