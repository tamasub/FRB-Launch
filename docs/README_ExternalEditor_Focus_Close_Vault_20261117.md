# FRB Launch — 外部エディター第3列・安定化差分 第3弾

対象：`launch_app_20261117_135958.zip` に、前回の
`FRBLaunch_Obsidian_Sakura_Stability_MultiFile_20261117_diff.zip` を適用した状態。
そのフォルダーへ本差分ZIPの `src/` を上書きしてください。

## 修正点

1. **サクラエディタのフォーカス誤移動**
   - ダブルクリック後、Launchが意図的にFiles Listへフォーカスを戻す処理を、外部エディター経路から撤去。
   - サクラエディタ・Obsidianの埋め込み編集中は、Qtの非アクティブ判定やLaunchの外側クリック判定で自動的にLaunchを閉じないようにした。
   - エディター領域をクリックしてから文字入力してください。ダブルクリック直後の自動フォーカス取得は、Windows実機で検証が必要です。
2. **第3列の×で外部エディターを通常終了**
   - 従来の「不可視ウィンドウとして保持」を、外部アプリだけ廃止。捕捉した編集ウィンドウと退避済み編集ウィンドウへWindows標準の `WM_CLOSE` を送る。
   - 画面を一度デスクトップへ復帰してから終了要求するため、未保存ならアプリ側の保存確認を利用できる。強制プロセス終了は行わない。
   - タブ共用時など、同じプロセス内に別ウィンドウがある場合はプロセスが残ることがある。*「× = プロセス強制終了」ではない*。他の作業を巻き込まないための安全策。
   - 起動検出待ち中は×を保留する（未検出プロセスの残留防止）。外部ウィンドウ表示後に再度×を押してください。
   - **FRB Studio自身**は従来の「×で非表示、未保存編集状態保持」を維持。
3. **Obsidian URIのVault解決方法を変更**
   - Obsidian登録済みVaultのIDとVault内相対ファイルパスを指定：`obsidian://open?vault=<id>&file=<relative>&paneType=window`。
   - URI直前にVaultが未登録になっていた場合はエラーをUI内に表示して外部URIを送信しない。
   - Obsidianの新規ポップアウト検出待ち上限を短縮。

## Windows実機で確認してほしいこと

1. 編集内容が失われると困るファイルは使わず、コピーした `a.txt` / `b.txt` / `c.ini` で確認。
2. `a.txt` → 第3列のサクラエディタ内をクリック → 文字を入力 → Ctrl+S。Files Listへ文字が入らず、Launchも飛び出し・終了しないか。
3. `b.txt` → `c.ini` に切替後も編集・保存できるか。
4. 内容を変更して **未保存** の状態で第3列の×を押す。デスクトップ上に元アプリの保存確認が表示され、キャンセルならアプリが見える状態で残るか。
5. Ctrl+S保存後に×を押し、該当エディターウィンドウが閉じるか。ほかのサクラエディタの作業は巻き込まないか。
6. 登録済みObsidian Vault内のテスト `.md` で同様に開くか。Vaultエラーが出る場合はVaultをObsidian本体から一度開き、Vaultの場所が正しいか確認。
7. `.json` → FRB Studio、URL → Browser Preview、Launch設定画面などがこれまでどおり動くか。

**重要：** スクリーンショットではObsidianのサイドバーに `$RECYCLE.BIN` や `FRB_Apps` が見えているため、ドライブ直下をVaultにしている可能性がある。ドライブ全体は監視・索引の負荷が大きくなり得るので、実験用の小さなVaultを別に用意する方が安定性の切り分けがしやすい。

## テスト

Linux上でPython構文検査・関連pytest 65件PASS。Windows実機の入力、`SetParent` の挙動、保存確認、Obsidian URI成否は未検証。

変更した本体：`src/app.py`、`src/expanded_view.py`、`src/studio_preview_panel.py`、`src/studio_win32_host.py`、`src/external_preview_route.py`。
追加テスト：`tests/test_external_editor_focus_close_v2_20261117.py`。

元データ・設定JSON・C# Studioのファイルは変更していない。
