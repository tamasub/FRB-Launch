# Obsidian: 同一ポップアウト再利用・新規作成禁止（2026-11-18）

## 適用元

`launch_app_20261118_200346.zip`。本差分をLaunchルートに上書きする。Studio側の変更・再ビルドは不要。

## 基本契約

- **初回のMarkdown**：Obsidianに登録済みのVault内で、従来と同じ `obsidian://open?...&paneType=window` を**1度だけ**要求する。
- **第3列で収容済み**：同じポップアウトのLeafを公式CLIで切り替える。新たな `paneType=window` を要求しない。
- **収容直前の連続ダブルクリック**：最初のウィンドウの収容・CLIバインドが完了するまで待ち、最後に選んだMarkdownをその同じウィンドウへ渡す。
- **CLIが使用不可／異なるVault／対象の特定失敗／切替結果が不明**：**新しいObsidian窓は作成しない**。旧ドキュメントを保持して第3列に状態メッセージを出す。成功したふりをしない。
- **Studioなどへ一時的に切り替えた場合**：既存のObsidianウィンドウを非表示退避。次回は別のMarkdownを選んでも退避済みの**同一HWND**を再収容し、以前のLeafを識別してから切り替える。
- **第3列の「×」**：従来どおりObsidianに通常の終了処理を依頼する。明示的に閉じた後の次回Markdownは新規セッションとして扱う。ユーザー操作による通常終了と、自動切替に伴う退避は区別する。
- **Launchの終了**：既存の終了処理が収容中・退避中の外部ウィンドウを復元する。

## 今回の変更対象外

- Obsidian本体、Vault、プラグイン、workspace.json、サイドバーの設定を変更しない。
- FRB Studio／サクラエディタのプロセス制御や切替契約は変更しない。
- 初回起動におけるObsidian自身の前面表示を完全には防げない。120/400msのLaunch前面化タイマーは除去し、収容成功時の一度だけ前面を戻す。
- Windows上の実画面でのチラつき、対象VaultのCLI対応は未検証。

## Windows実機での確認順序

1. 第3列で `A.md` を開く。Obsidianの専用窓が1つだけ収容されることを確認。
2. `B.md` → `C.md` → `A.md` を続けて開く。窓を増やさず同じ第3列で切り替わることを確認。
3. ダブルクリックを連続で繰り返し、ウィンドウが増えないことを確認。
4. `A.md` を表示 → JSONでStudioへ切替 → `B.md` に戻る。退避したObsidian窓の再利用とBへの切替を確認。
5. CLI無効化や別VaultのMarkdown選択時、新しいウィンドウが生成されず旧ドキュメントが残り、警告が出ることを確認。
6. 第3列「×」でObsidianが通常終了することと、閉じた後の次回起動が新規セッションになることを確認。未保存データではObsidian側の確認を尊重する。

## テスト

- `python -m pytest -q tests/test_obsidian_one_popup_invariant_20261118.py tests/test_obsidian_dock_bridge_20261118.py`
- 追加の状態遷移テスト12件を実行。
- Obsidian／外部エディター関連の広いテストは `135 passed, 20 failed`。失敗20件は**適用元でもすべて同じ**。既存の古いWinEvent/Sakura仕様を前提にしたテスト等。
- `python -m py_compile src/studio_preview_panel.py` 成功。

## ロールバック

本差分の `src/studio_preview_panel.py` だけを、適用元のZIP内の同名ファイルに戻す。
