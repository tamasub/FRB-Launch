# FRB Launch — VS Code 縁台Overlay 試作 / 2026-11-19

## 適用基準

- 元ソースZIP：`launch_app_20261119_153327.zip` **そのまま**（過去差分の上からの重複適用を想定しない）
- 適用：差分ZIPを **Launchアプリのルート**へ展開・上書き → Windows上のLaunchを終了してから起動
- `FRB Studio` C#側の変更・再ビルド：不要
- **Obsidian、Browser、Studio、サクラの既存の経路は原則そのまま**。通常の`_run_windows.bat`では今回のVS Code試作機能は無効

## 起動方法（Windowsでの実験）

1. 普通のVS Codeに未保存の編集があれば保存／作業継続できる状態にしておく。
2. Launchを完全終了する。
3. 追加した **`_run_windows_Try_VSCode_Overlay.bat`** を起動する。
4. Files Listで `.py` / `.js` / `.ts` / `.html` / `.css` などを**ダブルクリック、またはEnter**する。
5. 新規のVS Codeウィンドウが現れたら、そのHWNDを実際のファイル名付きタイトルで確認してから、**Launch第3列へ非親子化Overlay表示**する。
6. 別のコードファイルを開くと、**同じ専用VS Codeセッションへ `--reuse-window` で依頼**する。タイトル更新を観測して切替を確認する。
7. 第3列の「外出し」アイコンで通常の独立ウィンドウへ戻す。×は**ゲストを終了せずに一時非表示**（再選択すれば復帰）。Launchの正常終了ではゲストをデスクトップへ復元。

**普段のLaunchを変更せず**実験を止める場合は、`_run_windows.bat` に戻す。

## なぜ専用のVS Codeユーザーデータ領域か

VS CodeのCLI `--reuse-window` は既存の「最後にアクティブだったVS Code」へファイルを開くことがある。普段のVS Codeで開いているウィンドウをLaunchが勝手に奪わないため、Launchごとに一意の `--user-data-dir` を指定する。初回は `--new-window`、以後は **同じ** `--user-data-dir` と `--reuse-window`。

ユーザーデータ：`%LOCALAPPDATA%\FRBLaunch\VSCodeGuest\launch-<UUID>\`。**専用環境なので最初は普段のVS Codeのユーザー設定／拡張機能／テーマが引き継がれない場合がある。** プロファイルは自動削除しない。既存のユーザープロファイルの変更も行わない。

## 対象ファイル

- VS Code：`.py`, `.pyw`, `.js`, `.mjs`, `.cjs`, `.jsx`, `.ts`, `.tsx`, `.html`, `.css`, `.java`, `.go`, `.rs`, `.cs`, `.sql`, `.yml`, `.yaml`, `.xml`, `.jsonc`, `.code-workspace` など。試験BAT起動時のみ。
- `.json`：Studioの`view_def`解決により**Studio管理対象なら従来どおりStudio**。それ以外はVS Code。Studioルート未設定ならJSONの自動切替は行わない。
- `.md`：従来どおりObsidian。
- `.txt`/`.ini`：従来どおりサクラ（またはWindowsの通常の関連付け）。
- フォルダーのEnter／ダブルクリック：これまでどおりFilesで移動する（VS Codeに取り込まない）。
- `My Work`などの**アプリ起動メニュー自体の動作は変更しない**。今回の試作は、Files Listからの物理コードファイルを対象とする。

## 安全策／まだ実機確認できていないこと

- 起動前のCode.exeトップレベルHWNDをSnapshot。**新規出現＋Code.exeプロセス＋目的ファイル名を含むタイトルが一意**でなければ、収容しない（通常のデスクトップに残す）。
- タイムアウトやウィンドウ特定失敗で**別窓を連続生成しない**。
- 非親子化Overlayなので `SetParent` しない。Obsidianで成功した **Launch位置追従（160ms）、Z-order、IME、ネイティブ検索履歴優先**の実装を共用する。ただしVS Codeでの実機結果は未検証。
- ×/切替では `WM_CLOSE`、プロセスkill、無断保存をしない。Launcher外出し後のウィンドウは、次回のLaunchゲストとして**再取得しない**。
- **実機未検証**：Code.exe起動オプション、ファイル名のタイトル表現、コマンドによる切替、IME候補位置、ポップアップ前後関係、Launch移動／最大化／最小化、外出し、復帰。失敗時は通常起動に戻す。
- 失敗時の簡易ローカルログ：`%LOCALAPPDATA%\FRBLaunch\vscode_guest_trace.jsonl`。タイムスタンプ・イベント・HWND・ファイル名だけを記録（文書の内容は保存しない）。共有前にファイル名を確認すること。

## 手動合格基準

1. 普段のVS Codeを開いておく → Launchから`a.py` → 別の**専用**VS Codeが第3列に見える（既存窓を盗まない）。
2. `b.js`→`c.ts`→`a.py` → 同じ第3列ゲストで切替、ウィンドウの増殖なし。
3. 日本語IMEの候補が編集カーソル付近。Chromeを前面に出したら自然に背後、検索履歴を開いたら検索履歴が優先。
4. Launch移動・最小化・最大化、×で退避→再選択、外出し、Launch終了のそれぞれで、未保存コードを失わない。
5. `.md` はObsidian、Studio管理JSONはStudioに残る。

## 静的／モックテスト

- `python -m pytest -q tests/test_vscode_guest_overlay_20261119.py`
- 修正時：専用 **23件PASS**。既存関連を含め **165件PASS・元ZIPでも同じ失敗3件**（旧Browser Previewと古いObsidian起動前提のテスト）。Windows GUI／VS Code実機未検証。
