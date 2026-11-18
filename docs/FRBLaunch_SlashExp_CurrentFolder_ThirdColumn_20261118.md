# FRB Launch / 矢印ナビ・第3列 改修差分（2026-11-18）

基準: `launch_app_20261118_152406.zip`。変更したファイルだけを同じ相対パスへ上書きする。UTF-8で保存。

## 変更した操作仕様

1. `/` メニューの初期位置を Exp ビューポート基準で17px左へ寄せ、背面の Exp 表示が覗く余白を削減。
2. `/` の最初の列に **（カレントフォルダー）** を先頭行として追加。検索欄の下に置く。実際の Files List の現在位置から取得し、Exp のハイライト行は参照しない。**→** で既存のフォルダー（または仮想JSONフォルダー）のコンテキストメニューへ進み、操作項目を選んで Enter で実行する。ここで Enter を押しただけでは実行しない。カレントが存在しない場合は誤ったフォルダーを操作させないため追加しない。
3. Files List の **Shift+↑ / Shift+↓** で選択範囲を拡大・縮小。通常の矢印移動と区別し、フォルダーを開かない。通常のクリック・矢印移動で範囲アンカーをリセットする。
4. Browser / Studio / Obsidian の第3列を開閉した後、実際の Exp/List 分割バー位置からぐりぐりボタンを再配置する。遅延レイアウトの反映も行う。
5. Obsidian の新規ウィンドウを確認して収容する直前に隠し、Launch のフォーカス回復を短時間試行。既存の Obsidian 窓は触らない。OSの前面化規則・既存プロセス再利用によりちらつきを完全には防げない。
6. Obsidian の新規収容ウィンドウへ Windows DWM の**明色フレーム**指定を試行。**Obsidianが内部に描画する黒いツールバーやテーマまでは変更しない**。Vaultの設定は書き換えない。
7. 第3列に収容した Obsidian の HWND が消失した、または収容に失敗して中身のウィンドウがないとき、第3列を自動で隠す。タブ0件等を推測して閉じることはしない（未保存タブ保護）。
8. Studio の第3列に、Browser と同じ `external` アイコンを用いた外出しボタンを追加。Studio は **Launch が所有権の解除をACKした後だけ** Win32 の親子関係を解消して外出しする。ACKできなければStudioを収容したまま中止。サクラエディタの従来の外出しは維持。

## 重要: Studio 側の差分が必要

⑧のStudio外出しを有効にするには、**別ZIP（Studio側）の `NativeShell/NativeShellForm.cs` も適用し、NativeShellを再ビルド**する必要がある。

Studioルートで PowerShell を実行:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build/Build-NativeShell.ps1
```

Launchのプレビューは `FRBStudio_App/NativeShell/_publish/FRBStudio.NativeShell.exe` を使用する。古い NativeShell のまま外出しを試みた場合は、Studio は手元に残してエラー表示する（安全側）。

## 検証と注意

- 変更したPythonファイルの `py_compile`: PASS
- `/` UIテスト: 37件（既存35＋追加2）、横断契約テスト4件: PASS
- Studioプレビュー・外部エディタ・ぐりぐり等の関連テスト（対象13ファイル）: **125 PASS / 1 FAIL**。その1件は変更前ZIPでも同じ失敗（旧 `embedded.sync_current_directory(directory)` 文字列前提のテスト）。
- Studio側 C# のOwner監視と解除コマンドに関する Node 静的契約テスト: 7 PASS。
- **Windows GUI実機検証と C# 再ビルドはこの環境では未実施**。Qt Native のキーフォーカス、Obsidianの前面化・枠色、第3列の位置、Studio外出し後のプロセス存続を実機で確認すること。

副作用回避: JSONデータ、保存済みユーザー設定、ローカルファイルは変更しない。外部Obsidianのテーマを強制変更しない。Studioは編集内容を保ったまま外出しする。
