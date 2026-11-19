# FRB Launch / Obsidian本体ウィンドウ収容（2026-11-18 試作）

## 基準

`launch_app_20261118_202041.zip` の差分。Launch側のみの修正。Studio NativeShellの再ビルド不要。

## 判断

「ポップアウトウィンドウを作って第3列へ入れる」のは誤った構造だった。Launch側から `paneType=window` を送ることを禁止し、**Obsidian Vault本体ウィンドウだけ**を取り込む。左側のファイル一覧は Obsidian標準の `app.workspace.leftSplit.collapse()` で閉じる。ObsidianのVault設定ファイル、外観設定、ショートカット、プラグインには書き込まない。

## 新しい経路

1. 初回 `.md` → 登録済みVaultとObsidian公式CLI（Obsidian.com）の存在を検証。
2. `obsidian://open?vault=<VaultID>` で**本体Vaultを開く／フォーカス**。ファイル指定・`paneType=window` は送らない。
3. CLI `eval` のバックグラウンド処理でメインの root leaf（ポップアウト以外）に対象のMarkdownを `openFile()` する。既存のleafを再使用。
4. CLIが返す本体 `document.title` に完全一致するObsidian.exeトップレベルHWNDが**一つだけ**ある場合のみ、Win32 `SetParent` で第3列へ収容。あいまいなら収容しない。
5. 収容後、同じ本体leafにセッショントークンを付与し、左サイドバーを `collapse()`。以降の `.md` は同じleafの `openFile()` で切り替える（新規ウィンドウ・新規タブは作らない）。
6. 第3列の「×」は、本体ウィンドウをデスクトップに戻す。**Obsidian.exeにWM_CLOSEを送らない**。Launch正常終了時も収容済み/退避中のウィンドウを復元。

## 制約と残課題

- **Windows＋PySide6＋Obsidian実機のGUI検証は未実施。** CLIの`eval`がObsidian 1.14などの実環境でメインの`document.title`を返し、Win32 HWNDのウィンドウタイトルと一致するか、初回に確認が必要。単にタイトルが似ているだけのHWNDを取り込む実装にはしない。
- 既存ポップアウトは自動で閉じない。前バージョンで残ったポップアウトに未保存の内容があればユーザーが処理してから試すこと。
- 最初のVault本体のフォーカス表示は一瞬発生し得る。余計な窓を生成しないことを優先。
- 別VaultのMarkdownを開く場合、同じ本体ウィンドウではないため安全側で切替を拒否する。Vault切替UIは今後検討。
- 共有オブジェクト・既存Studio／サクラの起動経路は変更しない。Obsidian公式CLIの利用設定は前回同様ONにする。
- 今回のテストは状態遷移・Node.jsでのObsidian API模擬・静的回帰。Windows上での描画やフォーカスは検証できない。

## Windowsでの確認順

1. 前バージョンが作ったポップアウトがあれば、編集状況を確認して閉じる。
2. Launchを再起動し、Obsidianのメイン画面をデスクトップに表示した状態で `A.md` をダブルクリック。第3列へ**メイン画面そのもの**が入ること、左サイドバーが閉じることを確認。
3. `B.md`、`C.md`、`A.md` と連続で開き、Obsidianウィンドウ数が増えないことを確認。
4. 第3列の「×」でObsidian本体が正常にデスクトップへ戻ること、Launch終了後も残ることを確認。
5. 複数Vault/同一ウィンドウタイトルで識別できなければ、Obsidianを元のウィンドウとして維持し、第3列に理由を出す。

## テスト

`PYTHONPATH=src pytest -q tests/test_obsidian_main_window_dock_20261118.py ...` など。既存のobsoleteポップアウト前提テストは新しい仕様に合わせて期待値を更新。
