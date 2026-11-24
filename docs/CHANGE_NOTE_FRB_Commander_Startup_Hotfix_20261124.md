# Commander 起動障害修正 2026-11-24
- Actual: 初期化途中の eventFilter が未生成 self.search を参照し AttributeError。QHBoxLayout の生成も失敗。
- Expected: 初期化中のイベントは基底クラスへ委譲し、全依存ウィジェット生成後にフィルターを登録・有効化する。
- 候補の別ウィンドウ化、キー操作、設定は変更しない。
- 回帰: Commander 関連 16 PASS / 1 SKIP (PySide6 不在)。初期化前の実メソッドを最小基底クラスで実行するテストと登録順序テストを追加。Windows GUI は未検証。
- 適用: Launch 終了後、ルートへ上書き展開して再起動。
