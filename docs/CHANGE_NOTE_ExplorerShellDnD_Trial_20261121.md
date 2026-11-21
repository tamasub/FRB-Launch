# FRB Launch — Explorer式D&D 比較試験（2026-11-21）

## 目的

FRB Launchからサクラエディタへファイルをドラッグするとパス文字列が挿入されるが、Shiftを押しながらドラッグするとファイルが開く、という実機報告に対応する。

期待値は「**ファイルがサクラエディタで開かれ、中身が表示される**」であり、「ファイル本文を現在の文書へ貼り付ける」ではない。

**既存のほかのアプリへのD&Dを壊さない**ことを第一制約とする。

## 技術的な判断

- 既存 `src/file_drag.py` は Qt `QMimeData.setUrls()` + `QDrag` の **COPY専用**。
- 実機診断では、Explorerに `Shell IDList Array` / `FileNameW` 等があり、LaunchにはURLとURL由来のテキスト表現が見えた。これだけでは原因は断定できない。
- Shiftの押下を模倣したり、Launchの許可動作をMOVEへ変更したりすると、Explorer等にドロップしたファイルが**移動される危険**があるため採用しない。
- サクラエディタの公開ソースでは、ファイルを開くD&D経路は `CF_HDROP` を使用し、`DROPEFFECT_LINK` を受ける経路がある。このため、Windows Shell由来のファイルデータを **COPY | LINK（MOVE禁止）** で渡す比較実験とする。LINKは参照の意味であり、サクラエディタが必ず開くという保証はない。

## 変更内容

1. Files Listの検索欄右側にある旧「本文D&D」ボタンを **「Explorer D&D」** へ置換。
2. 起動時 **OFF**。OFFでは元のQtのファイルURL D&Dを完全維持。
3. ON時のみ `src/native_shell_drag.py` で `ILCreateFromPathW` → `SHCreateShellItemArrayFromIDLists` → `IShellItemArray::BindToHandler(BHID_DataObject)` → `SHDoDragDrop` を呼び出す。ファイル本文は読まない。
4. 既存のデータオブジェクトが初期化できない場合、通常Qt方式にフォールバック。キャンセル時は二重ドラッグしない。
5. Files List以外（Exp列、他のLaunch項目等）のD&Dは変更しない。旧 `src/file_drag_text.py` が残っていても未使用。
6. COPYとLINKのみ許可し、**MOVEは一切許可しない**。ただしON時は他アプリのD&Dの挙動が変わる可能性があるため、検証が終わればOFFに戻すこと。

## 適用・実機検証

ベース：`launch_app_20261121_105705.zip`。Launch完全終了後、差分ZIPをルートへ上書きして再起動。

1. **Explorer D&D OFF** のまま、普段どおりのExplorer・VS CodeなどへのD&Dが維持されていることを確認。
2. OFFのままサクラエディタへ `.txt` ファイルをドロップし、これまでのパス挿入を確認。
3. **Explorer D&D ON** にして、同じ `.txt` を **Shiftキーを押さずに**サクラエディタの編集領域へドロップ。
4. 期待値：サクラエディタがそのファイルを開く（文書中にパスや本文を貼り付けるのではない）。
5. ONモードでExplorerなどへのドロップは意図せぬリンク作成があり得るため、まずはサクラエディタだけで試す。
6. 検証後は **OFF** に戻す。

## 自動テスト

- `tests/test_text_drag_opt_in_20261121.py` を新方式のテストに入れ替え。通常時のURL＋COPY、ON時だけShell分岐、事前エラー時のフォールバック、複数ファイル、MOVE禁止、画面のOFF初期状態をチェック。
- 今回対象のテスト群で **15件PASS・既存失敗1件**（旧Files List罫線描画の文字列チェック）。この失敗は添付元の `src/expanded_view.py` でも同じ。
- 広めの関連テストでは、元ZIP **12件PASS・2件失敗・2件SKIP**に対し、改修後 **20件PASS・同じ2件失敗・2件SKIP**。今回新規の失敗ゼロ。
- Windows上の `SHDoDragDrop` とサクラエディタでの実ドロップは、この実行環境では未検証。

**今回の差分は本対策採用前の比較実験版**。実機で「Shiftなしでもファイルが開く」が確認できた場合にのみ、標準化を検討する。
