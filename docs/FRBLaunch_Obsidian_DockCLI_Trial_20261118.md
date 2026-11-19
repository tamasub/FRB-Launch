# FRB Launch — Obsidian第3列・専用ポップアウト再利用試作（2026-11-18）

## 基準ZIPと適用

- 基準: `launch_app_20261118_191715.zip`
- 差分ZIP内の相対パスをLaunchルートへ上書き。JSONデータ、ObsidianのVault設定、Studio NativeShellは変更しない。
- Studio側の再ビルド不要。Launchを再起動する。

## ねらい

1. `.md` 初回ダブルクリック: **これまでどおり** `obsidian://open?...&paneType=window` で新規ポップアウトを作り、第3列に収容。既存デスクトップのObsidianは取り込まない。
2. 収容したポップアウトのノートが一意に特定できた場合に限り、Obsidian公式CLIの `eval` でその編集領域に一時的な目印（実行中メモリ上のトークン）を付ける。
3. そのポップアウト自身の左サイドバーが開いていると判断できた場合だけ、標準のトグルボタンをクリック。既に閉じていれば何もしない。CSSが変わり判定できない場合も何もしない。
4. **同じ登録済みVault内** の次の `.md` は、目印の付いた編集領域に対して `WorkspaceLeaf.openFile()` を使って切り替える。新しいポップアウトは作らない。
5. 初回のCLI接続が不可なら、従来の新規ポップアウト方式へ戻る。実行タイムアウトなど結果不明の切替時は、勝手に追加の窓を開かずエラー表示する。

## 初回のみ必要なObsidian設定

Obsidian の **設定 → 一般 → Command line interface（コマンドラインインターフェース）** を有効にする。公式の **1.12.7以降のインストーラー** が必要。Launchは `Obsidian.exe` と同じフォルダーの `Obsidian.com` を探す（環境変数 `FRB_LAUNCH_OBSIDIAN_CLI` に実ファイルを明示することも可能）。**Advanced URIプラグインは不要。**

CLIが無効・未導入でもLaunchは従来方式で動く（サイドバー自動制御と同一編集領域への切替はできない）。

## Windows実機での確認ポイント

1. Obsidianを起動し、テスト用の登録済みVaultに `A.md` と `B.md` を用意する。
2. LaunchでAをダブルクリックし、第3列に収容されるか見る。左のファイル一覧が閉じられたかを見る。
3. 続けて同じVaultのBをダブルクリック。**同じ第3列の同じObsidianウィンドウにBが現れるか**、新しい窓が増えないか確認する。
4. A→B→Aを繰り返す。編集・保存、既存のデスクトップObsidian、Studio/Sakuraに影響がないか見る。
5. Vaultの異なる `.md` や、複数のポップアウトに同じファイルが開いている場合は、安全側フォールバックが働くことを確認する。

## 制限と安全面

- 今回はWindows版ObsidianでのCLI実行・Qt収容を実機検証していない。Python/JS単体のテストのみ。
- 初回の新規ポップアウト作成と収容時の短い前面チラつきは、この改修では解消しない。
- 左サイドバーはアプリの内部DOM構造に依存する**ベストエフォート**。ObsidianのUI変更で閉じられないことはあるが、判定できない場合は無理に操作しない。
- Obsidianユーザー設定、Vaultの `.obsidian`、ショートカット、プラグインをLaunchから編集しない。
- 閉じた第3列の再表示や、Studio等へ移動した後の復元では初回のバインドが再実行される場合がある。動作不明ならいったん第3列を閉じて開き直す。
- 他社製アプリのポップアウトをWin32で収容する機構自体は従来のまま。Obsidianの非公開UIやIPCの将来的な変更への対応は別途。

## 変更ファイル

- `src/studio_preview_panel.py` — Obsidian限定の非同期CLI連携、同一編集領域切替、失敗時の安全処理
- `src/obsidian_dock_bridge.py` — 登録済みVaultとCLI検出、ウィンドウ識別、サイドバー判定、CLI呼び出し
- `tests/test_obsidian_dock_bridge_20261118.py` — JSモック/CLIモックを含むテスト
- `docs/FRBLaunch_Obsidian_DockCLI_Trial_20261118.md` — 本書

## 差分の戻し方

基準ZIPから `src/studio_preview_panel.py` を復元し、追加した `src/obsidian_dock_bridge.py` を削除してLaunchを再起動する。
