# FRB Launch — External Editors in Third Column（試作）

対象: 2026-11-17 時点の Launch（「第3列Studio + 設定収容 + Launchメニュー設定タイトル修正」適用済み）

## 操作

| Files List ダブルクリック対象 | 第3列 | 備考 |
|---|---|---|
| `.md`（Obsidian Vault内） | Obsidian の新しいポップアウト | `obsidian://open?path=...&paneType=window` |
| `.md`（Vault外） | 従来どおり Markdown Studio | 安全なフォールバック |
| `.md`（Shift + ダブルクリック） | 従来どおり Markdown Studio | Vault内でも明示的にStudioを選択 |
| `.txt` / `.ini` | サクラエディタ | `sakura.exe -- <ファイルパス>` |
| Studioが管理する `.json` | 従来どおり FRB Studio | 保存処理不変更 |
| URL | 従来どおり Browser Preview | 不変更 |

`.txt` / `.ini` でサクラエディタが見つからない場合は、従来の開く処理へ戻す。
ファイルの関連付けやStudioの既存起動方法、Enter操作は変更しない。

## アプリ検出

- Obsidian: 標準Windows `obsidian://` URIハンドラを使用。対象の先祖フォルダーに `.obsidian` がある場合のみ対象とする。アプリ側でもVaultが登録されている必要がある。カスタム設定フォルダーを用いるVaultはこの試作では自動識別しない。
- サクラエディタ: PATH、Windowsの App Paths、ファイルの「プログラムから開く」の登録情報、主なインストール先を確認する。
- いずれもプログラムが見つからない場合はデータを変更しない。
- サクラエディタがポータブル版などのために見つからない場合、Windows環境変数 `FRB_LAUNCH_SAKURA_EXE` に `sakura.exe` のフルパスを指定してLaunchを再起動する。

## Win32ウィンドウ収容の安全策

- **必ず起動前のHWND一覧を撮る。** 対象エディターの「新規に増えたウィンドウ」だけを収容候補とする。
- プロセス実行ファイル名と選択ファイルの名前（またはサクラ新規プロセスID）で追加照合する。
- すでに使っている既存Obsidian Vaultウィンドウや他ファイルの編集ウィンドウを収容しない。
- 曖昧な場合は収容しない。外部ウィンドウを強制終了しない。
- `×` は第三列の非表示のみ。別のファイルに切り替えたときは旧ウィンドウを隠して保持し、Launch終了時にデスクトップへ復帰。
- 保存はObsidian/サクラエディタ自身が担当。Launchはファイルを書き換えない。

## 確認すること（Windows実機）

1. ObsidianでVaultを開き、Vault内のテスト用 `.md` を Files List からダブルクリック。第3列が表示されるか。変更後に保存し、再読込して内容が残るか。
2. Vault外の `.md` は従来のMarkdown Studioで表示・保存できるか。Vault内でも Shift + ダブルクリックでStudioを選べるか。
3. テスト用 `.txt` / `.ini` をサクラエディタで開き、編集・保存・再読込できるか。
4. 第3列 `×` → 同じファイルで再表示、別のファイルに切り替え、Launch終了時の元ウィンドウ復帰を確認。
5. すでに起動していたObsidianのVaultウィンドウが無断で第3列に吸い込まれないことを確認。
6. 従来のJSON Studio、Launchメニュー設定、オプション設定、Browser Previewが動作するか。

## 既知の制約

**Windows実機でのQt跨ぎWin32収容は未検証。** Qtホスト、Sakura(C++)、Obsidian(Electron) の描画・フォーカス・DPI相性は異なり、タイトルやウィンドウの再生成によりプレビューを検出できない場合がある。Obsidianが新規のポップアウトを生成しない場合、既存Vault画面は安全のため収容せず、第三列に説明を表示する。

UI挙動や既存保存処理を変更するためではなく、既存ネイティブ編集画面を共通ホストへ収容できるか検証する目的の試作。
