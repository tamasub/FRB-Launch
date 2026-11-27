# FRB Launch — 選択UI・処理中表示の共通化（2026-11-27）

基準: launch_app_20261127_201020.zip。差分を同じ相対パスへ上書きする。

## 責務と共通Expected

- `src/menu_lifecycle.py`: 終端操作の判別、所有する選択UIの閉鎖、処理の発行。業務処理の終了待ちでメニューを表示し続けない。階層展開・候補探索は終了扱いにしない。後続のインライン編集を必要とするホストは維持する。
- `src/processing_display.py`: 砂時計、MESSAGE、PROGRESSの表示と解除。標準CURSOR。NONEなし。正常終了・例外のどちらでも解除し、既存カーソルを保つ。人間の確認待ちは処理中とは区別する。
- 既存 `FilesOperationProgress` を共通表示サービスのダイアログとして再利用。MESSAGEは進捗欄を隠す。コピー・移動・削除のPROGRESSを維持する。
- 既存の個別処理の内容は維持。操作確定前の検索・階層移動は処理中表示の対象外。バッチコマンダー本体や実行処理、ファイル索引の状態表示・内部状態管理は今回対象外。

## 適用・モード

Files Exp/List、設定歯車、Launch JSON、Remote、Keyboard Ex、ぐりぐり、カスケード、ブックマーク、タスクトレイ、Commander候補選択の既存経路を共通処理に接続。

- CURSOR: 標準。すべて展開、短時間処理、外部機能への引き渡しを含む。
- PROGRESS: Launchが実行する既存のコピー・移動・削除。Shellへ委譲する仮想クリップボード貼り付けはShellの画面と二重表示しない。
- MESSAGE: Gitコミット本処理。アプリ一覧・ファイル索引のバックグラウンド更新は既存の非ブロッキング動作を維持し、今回の更新要求はCURSORまで。後者の継続状態は別責務。
- マウス・Enter・ぐりぐり・Keyboard Exの確定を共通発行経路へ寄せた。プログラムから直接QAction.trigger()する経路に対しては終端閉鎖のフォールバックもあるが、全直接呼び出しの砂時計表示まで保証できていない。

## テスト

`python -m compileall -q src` 成功。

```
$ PYTHONPATH=src pytest -q tests/test_menu_lifecycle_processing_20261127.py tests/test_menu_lifecycle_qt_20261127.py tests/test_remote_context_wheel_prototype_20261103.py tests/test_context_menu_wheel_click_20261108.py tests/test_files_current_singleton_and_context_close_20261102.py tests/test_launch_json_context_popup_lifetime_20261111.py tests/test_files_exp_file_doubleclick_menu_close_20261102.py
41 passed, 2 failed, 1 skipped
```

新規のQt不要共通責務テスト10件は全通過。従来の個別閉鎖期待・遅延グローバル閉鎖を前提にしたテストを共通責務の期待へ更新した。残る2件は元ZIPにも存在する失敗: `test_popup_grab_wheel_redirected_by_pointer_position`、`test_blank_click_remembers_outline_but_does_not_select_a_paste_target`。今回は別の責務として未修正。全テストは未実行。PySide6がないためQt実画面テストはスキップ（同梱）。Windows実機検証は未実施。

## Windowsでの受入確認

- Newフォルダー/テキスト/Markdown: メニューが消え、作成後の名前編集にフォーカスが移る。
- 設定メニューの子階層を展開中は残り、操作確定時は所有するメニュー階層のみ閉じる。
- Keyboard Ex・ぐりぐり・通常右クリックで同じ操作を実行。二重実行・残存メニュー・無関係なUI閉鎖がない。
- コピー/移動/削除/キャンセル/エラー時に表示が残らない。Gitはメッセージ表示、ZIP展開はCURSOR。極短時間のCURSORの視覚的な描画はOS・イベント処理タイミングにも依存するため実機確認。
- Commanderの一時選択UIのみ閉じ、本体・バッチ処理実行には影響しない。索引状態画面は従来のまま。
