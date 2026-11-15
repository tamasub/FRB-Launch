# FRB Launch 0.9.5 — GitHub更新テスト手順

更新日: 2026-11-14  
対象: Windows 11 / Windows PowerShell 5.1  
今回の検証: 統合版 **0.9.4 → 0.9.5**、Launch **0.9.2 → 0.9.3**、Studio **0.9.0 → 0.9.0**、Updater **0.9.4 → 0.9.5**。

## 大事な前提

- `FRB Launch` のソース、Studio、開発環境、テスト環境はこれまでどおり別のまま扱う。
- GitHubに公開する初期テンプレートの**個人用メニュー・ローカルパス・通常のURLは含めてよい**（開発者承認済み）。ただし認証情報は公開対象外。スクリプトはJSON内の代表的な認証情報を簡易チェックするが、すべての秘密情報の存在を保証する検査ではない。
- **公開GitHubリポジトリ**を使う。非公開リポジトリのRelease Assetは通常の匿名HTTPSダウンロードに使用できない。
- 今回は **Pre-release**。`releases/latest/download/...` は使用せず、固定タグ `v0.9.5` のURLを使う。
- このパッケージはGitHubへのアップロード実行そのものは含まない。アップロードはWindows上で`-PublishRelease`を指定したときだけ行う。
- 更新実行は**Launchの「更新を開始」ボタンを押したときだけ**。スクリプトはインストールされたSystemを自動更新しない。

## 0. 初回だけ: GitHub側の準備

GitHub CLI (`gh`) が未インストールなら、Windowsで以下を実行する。

```powershell
winget install GitHub.cli
```

ターミナルを開き直し、ログイン。

```powershell
gh auth login
```

新規の専用リポジトリ名は例として **`tamasub/FRB-Launch`** を使用する。すでに別名の公開リポジトリがある場合は、各コマンドの`-Repo`をその名前に変更する。

リポジトリが存在しない場合は、GitHubのWeb画面から**公開リポジトリをREADME付きで作成**する。コマンドなら次の方法も可能。

```powershell
gh repo create tamasub/FRB-Launch --public --add-readme
```

同名リポジトリがすでに存在する場合、このコマンドは実行しない。

## 1. 添付ZIPをソースルートに展開

ZIPにある次のファイルを **`F:\FRB_Apps\FRB_Launch`** に配置する。

```text
prepare_FRBLaunch_0.9.5_GitHub_test.ps1
scripts\prepare_github_release_095.py
docs\README_GitHub_095_Test.md
```

※`tests/` は任意。展開先の既存ソースとUserDataを上書きするものではない。

## 2. 配布用ファイルを作成（GitHubにはまだアップロードしない）

Launch／Studioのビルドが済んでいて、Updaterも再ビルド済みであることを確認する。

```powershell
cd F:\FRB_Apps\FRB_Launch

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBLaunch_0.9.5_GitHub_test.ps1 `
  -Repo 'tamasub/FRB-Launch'
```

作成場所:

```text
F:\FRB_Apps\FRB_Release_Output\github_0.9.5\
  FRBLaunch_0.9.5_portable.zip
  FRBLaunch_0.9.5_update.zip
  FRBUpdater_0.9.5.exe
  SHA256_0.9.5.txt
  product_feed.json
  updater_feed.json
  RELEASE_NOTES_0.9.5.md
```

中断した場合は、同じコマンドを再実行して既存の配布ZIPを**検証して再利用**できる。異なるファイルを勝手に上書きしない。

`[SAFE] Prepared. Nothing uploaded or installed.` を確認する。

## 3. GitHub Pre-releaseにアップロード（明示実行）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBLaunch_0.9.5_GitHub_test.ps1 `
  -Repo 'tamasub/FRB-Launch' -PublishRelease
```

`v0.9.5` のPre-releaseを作成し、6ファイルをRelease Assetとして添付する。既存Pre-releaseがあれば不足Assetのみ追加する。サイズが異なる既存Assetは上書きせず停止。

**GitHub上のReleaseと匿名HTTPSで取得できるFeedを確認できるまで、次に進まない。**

公開先は、指定のリポジトリが使える場合のみ次の形式になる。

```text
https://github.com/tamasub/FRB-Launch/releases/tag/v0.9.5
```

## 4. テストインストールのFeedだけGitHubに切り替え

LaunchとStudioを終了する。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\prepare_FRBLaunch_0.9.5_GitHub_test.ps1 `
  -Repo 'tamasub/FRB-Launch' -ConfigureTestInstall
```

以下のファイルだけをバックアップ付きで更新する。

```text
F:\FRB_Update_Test\FRBLaunch\UserConfig\update_sources.json
```

- 更新先はGitHubの **HTTPS** Feed
- `allow_local_for_test = false`
- `F:\FRB_Apps\FRB_Launch` のソースやビルド成果物は変更しない
- 更新本体は実行しない
- インストール済み統合版が0.9.4でない場合／中断Journalがある場合は停止

## 5. 実際のGitHubダウンロード更新を確認

`F:\FRB_Update_Test\FRBLaunch\FRBLaunch.exe` を起動して「バージョン情報」を開く。自動で最新版照会が始まる想定。

1. 最新版 **統合版0.9.5 / Updater0.9.5** を表示できる。
2. 設定アイコン横の控えめな情報アイコンが表示される。
3. **「更新を開始」は人間が明示的にクリック**。
4. 進捗ウィンドウの表示・工程名・フォント・右端の整列を確認。
5. 進捗バーが100%で完了し、Launchが再起動する。
6. 統合版0.9.5 / Launch0.9.3 / Studio0.9.0を確認。
7. 更新後もGitHub HTTPS Feedが保持され「最新版を使用しています」と表示される。
8. Expの開発パス、ZIP作成メニュー、Studio詳細設定の起動を確認。

ローカルFeedへの復旧が必要なら、今回の設定バックアップを参照する。UpdaterのJournalやバックアップ領域はむやみに削除しない。

## 注意: 将来の自動バージョン検出

今回は固定タグ `v0.9.5` にある Feedを検証するため、0.9.6を公開しただけでは、この固定URLから新しい版は自動検出されない。

今後の継続運用では、GitHub Pagesまたは公開ブランチの `feeds/product_feed.json`／`feeds/updater_feed.json` に **安定したURL** を持たせ、配布のたびにその中身を更新する方式が必要。これはGitHub経由の初回更新テストに成功したあとに整備する。

## 重要な制限

- 配布・公開はユーザーのWindows上で明示実行。ここでGitHubに公開したわけではない。
- GitHub CLI／Windowsの実機での確認は未実施。
- 個人用のパス・URLはユーザーの指定どおり維持。公開後に削除しても、過去のダウンロード済みコピーまでは消せない点に注意。
