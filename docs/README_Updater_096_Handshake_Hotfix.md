# FRB Updater 0.9.6 起動許可データ競合修正

対象: GitHub Pre-release を利用した **統合版 0.9.4 → 0.9.5** の更新テスト。

## 起きた事象

GitHubの Feed／Updater EXE／更新ZIPのURL検証はすべて成功したが、Updater進捗画面で

> Updater起動許可データが不正です

と表示され更新前に停止した。

## 再現した原因

従来の `src/frb_update/progress_gate.py` は `activate()` で `.go` ファイルを直接作成し、その中に `start` を書く。

別プロセスの Updater はファイルがあることを検出すると直ちに中身を読むため、**ファイルの存在が先に見え、書き込み完了前に空文字列を読む競合** があり得る。

この競合条件をテストで強制すると、旧コードでは実際に同じエラーメッセージを再現。修正後は通過した。

ただし実際のWindows実機で今回のエラーの直接原因がこの競合だったかは、現時点では断定できない。

## 修正方針

- **Launch側**: `start\n` を一時ファイルに完全に書いて閉じ、`os.replace()` で原子的に公開。
- **Updater側**: 旧Launchが使う非原子的書き込みを考慮し、空／不完全な許可ファイルを最大1.5秒再確認。
- **Fail closed**: 不正データが続けば依然として停止。許可がなければ更新対象に一切触れない。
- **今回のGitHub更新テスト**: インストール済み旧Launchは更新前のため、特に Updater側の互換対策が効く。

## 配布の取り扱い

すでに公開済みの `v0.9.5` の統合版ZIP・Feed・Updater EXEは**絶対に上書きしない**。

今回は **Updaterだけ 0.9.6** とし、独立したPre-releaseを作成する。

- リリースタグ: `updater-v0.9.6-hotfix`
- GitHubアセット: `FRBUpdater_0.9.6.exe` と `updater_feed.json`
- 製品Feed: 既存の `v0.9.5/product_feed.json` を維持
- ローカルテスト先: `F:\FRB_Update_Test\FRBLaunch` のみ

統合版 0.9.5 / Launch 0.9.3 / Studio 0.9.0 は変更しない。

## 操作手順

### 1. 修正差分ZIPをソースルートに展開

`F:\FRB_Apps\FRB_Launch` へ上書き。変更する既存ソースは `src\frb_update\progress_gate.py` のみ。

### 2. Updater 0.9.6のビルドとローカル準備（公開しない）

```powershell
cd F:\FRB_Apps\FRB_Launch
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBUpdater_0.9.6_GitHub_hotfix.ps1
```

既存の `_build_updater_windows.bat` を使用する。Launch / Studio / 統合版ZIPはビルドし直さない。

### 3. Updater進捗画面だけを確認（安全なGUIテスト）

```powershell
& 'F:\FRB_Apps\FRB_Launch\dist\updater\FRBUpdater.exe' ui-test --show-progress
```

この操作は製品ファイルを変更しない。

### 4. GitHubへUpdater専用のPre-releaseを公開

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBUpdater_0.9.6_GitHub_hotfix.ps1 `
  -PublishHotfix
```

`gh auth login` 済みの Public リポジトリが前提。

### 5. テスト環境だけUpdater Feedを変更

**Launch / Studio を完全終了**させてから実行。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBUpdater_0.9.6_GitHub_hotfix.ps1 `
  -ConfigureTestInstall
```

既存 UserConfig のバックアップを取り、 `updater_feed_url` だけ更新。
`product_feed_url` は v0.9.5 を保持する。中断Journalがある場合は停止する。

### 6. GitHub経由で更新テスト

`F:\FRB_Update_Test\FRBLaunch\FRBLaunch.exe` から「バージョン情報」を開く。

期待値:

- 現在の統合版: **0.9.4**
- 最新の統合版: **0.9.5**
- 最新のUpdater: **0.9.6**

内容が合えば利用者操作で「更新を開始」。進捗バー、完了、Launch再起動、更新後0.9.5表示を確認する。

## 注意

- Windows実機でこの0.9.6修正版をまだビルド・公開・動作確認していない。
- Python側テストは追加6件、既存の更新関連21件にPASS。
- GitHub Releaseのソースアーカイブは必ずしもこのUpdater修正ソースと一致しない。今回はバイナリ検証向けPre-releaseなので、正式公開時はソースとタグの整合も別途確認する。
- 認証データの扱いを変更する修正のため、公開前のWindows実機更新テストで結果を必ず確認する。
- もし失敗しても、Journalが未完了なら再試行せず、先に復旧する。
