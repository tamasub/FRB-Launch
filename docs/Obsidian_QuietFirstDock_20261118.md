# FRB Launch — Obsidian初回入室のちらつき低減（試作）

## 適用元

- `launch_app_20261118_193842.zip`
- 差分ZIPをFRB Launchのルートに展開して上書き。
- Studio / ObsidianのバイナリやVault設定は変更しない。PythonのLaunchを再起動する。

## 対応範囲

前回成功している「サイドバーを閉じる」「2つ目のMarkdownを同じObsidianポップアウトで開く」は変更しない。初回のウィンドウ生成～収容までの一瞬の露出を減らす。

1. `obsidian://` URIを要求する**前**に、Windowsの `EVENT_OBJECT_SHOW` / `EVENT_OBJECT_NAMECHANGE` を監視開始。
2. 既存ウィンドウのHWNDスナップショットに含まれない、実行ファイル名が **Obsidian.exe** で、対象ファイル名に合う**新しいトップレベル窓のみ**早期に一時非表示。
3. 早期捕捉した非表示ウィンドウも収容対象の探索に含め、親ウィンドウを第3列へ付け替えてから表示する。
4. Windows通知の受信に失敗しても、従来の約350msごとのポーリングから**初回Obsidian限定で50ms**ごとの探索に変更して補完。
5. URI起動失敗、12秒の探索タイムアウト、SetParent失敗、Launch終了などでは、監視を解除し、隠した窓を**デスクトップへ再表示**する。

## 制約・非対象

- **「絶対に1フレームも表示しない」保証はない。** Windowsが最初に窓を描画する瞬間や、Obsidian既存メイン窓が前面に出る動作は完全には抑止できない。公式Obsidianに「非表示でポップアウトを開く」直接的な指示はない。
- 既存Obsidianのウィンドウを奪わない。Vault・ワークスペース・プラグイン・ホットキーも変更しない。
- 2ファイル目以降のCLI切替、サクラ、Studioは触らない。
- WinEventHookはWindowsネイティブ通知のため、Windows実機受入テストが必要。

## 受入確認（Windows）

1. FRB Launchを起動し、まだ第3列にObsidianがいない状態で任意の.mdをダブルクリック。以前より大きなウィンドウの露出が短く、第3列に正常表示されること。
2. `.md` A→B→A。左サイドバーが閉じたまま同じ窓で切り替わること。ウィンドウが増えないこと。
3. Obsidianの起動に失敗した場合も、空の非表示窓が残らないこと。
4. すでに外に開いている個別Obsidianウィンドウは隠れないこと。Studioとサクラも従来どおり。

## 検証

- `python -m py_compile` 対象3ファイル：PASS。
- `pytest` Obsidian/Studio/サクラ関連104件：98 PASS / 6 FAIL。6件は添付元ZIPでも同一の既存FAIL。
- 新テスト6件はPASS。Qt/PySide6とWindows/Electron実画面はこの検証環境では動作未確認。
