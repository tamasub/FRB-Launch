# FRB Launch 第3列 Obsidian 文字入力フォーカス修正（試作）

## 対象

- 基準: `launch_app_20261117_162843.zip`
- 変更対象: Launch側のみ。FRB Studio / Obsidian本体のソース・保存処理には手を加えない。
- 今回の範囲: **登録済みVault内の `.md` を第3列に収容した場合の文字入力**
- 保管庫外の `.md` の埋め込み対応は対象外。従来の外部起動・フォールバック動作を維持。
- Studio専用プロセスの再利用・スプラッシュ非表示はこの差分の対象外。

## 変更理由

ObsidianはQtとは別プロセスのElectronウィンドウを `SetParent` で第3列に収容しています。ウィンドウの表示成功とWindowsのキーボード入力フォーカス獲得は別であり、Launchの Files List に文字が送られる場合がありました。

## 変更

- `src/desktop_double_click.py`: 既存の低レベルマウスフックで、実際の左ボタンのリリースを受けた後にQtイベントループへ通知。フック内でWin32のフォーカス操作を行わない。
- `src/app.py`: 第3列Obsidian表示中に限ってマウス通知を受ける。通常のマウス・キーボード操作には影響させない。
- `src/studio_preview_panel.py`: 実際にObsidianを収容中であることを確認し、Win32フォーカス処理へ渡す。
- `src/studio_win32_host.py`: クリックされた実ウィンドウが、収容中のObsidian自身またはその子ウィンドウであることを検証。その場合だけ `AttachThreadInput`→`SetFocus`→解除を行う。既にElectron内で入力フォーカスがある場合には触れない。IME入力やキーボードイベントを合成しない。
- `tests/test_obsidian_embedded_native_focus_20261117.py`: Win32呼び出しをモックした安全確認。

## 適用方法

1. Launchを完全終了する。
2. ZIP内の `src/` 4ファイルをLaunchの `src/` に上書きする。既存の `src/` フォルダーを丸ごと置換・削除しないこと。
3. 必要なら `tests/` の追加テストを配置する。
4. 第3列収容を試す場合にのみ、既存の `%LOCALAPPDATA%\\FRBLaunch\\state.ini` の `[General]` に `embed_obsidian=true` を設定する（初期値OFFのままでよい）。
5. Launch再起動。

## Windows実機確認（必須）

1. **テスト用Vault内**で `note.md` をダブルクリックし、第3列にObsidianが表示されること。
2. Obsidian本文の編集箇所をマウスでクリックして `abc あいうえお` を入力。**Files Listの検索欄・選択行へ文字が流れない**こと。
3. 日本語IME変換、Backspace、矢印、Ctrl+Sを試し、保存後に再読込して内容が残ること。
4. 第3列以外をクリックしてFiles List操作へ戻り、再度本文をクリックして入力できること。
5. 第3列×、アプリ切替、Studio／サクラエディタの通常機能が従来どおりであること。

注意: Linux上ではWin32/Electronの実操作を検証できないため、**文字入力の解消は未確認の試作**です。うまくいかない場合はまずオプションをOFFに戻してください。終了時に未保存データがある場合の扱いはObsidian本体の保存仕様に従います。

## 検証

`pytest` を用いた関連テスト61件PASS、Python構文検査PASS。既存のデスクトップフックテスト1件は元ZIPでも同じ理由で失敗することを確認し、PASS数には含めていません。
