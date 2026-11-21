# FRB Launch — Files List Explorer D&D を正式標準化（2026-11-21）

## 背景・ユーザー実機結果

サクラエディタへファイルを通常ドラッグするとパスが挿入されていたが、試験スイッチ「Explorer D&D」ON で **Shift キーなしにファイルを開く**ことをユーザーが確認した。求める動作は「ファイルを開く」であり、本文を現在の文書へ貼り付けることではない。

## 対策

- Files Listの外部ファイルD&Dを **Windows Shell形式（前回成功した経路）** に標準化。
- 検索バー横の「Explorer D&D」試験ボタンを撤去。見た目のON/OFF判定も不要。
- その他のドラッグ経路、ファイル再並び替え、操作アクション等は変更しない。
- ファイル移動は要求しない。既存の `src/native_shell_drag.py` が `SHDoDragDrop` に渡す COPY 指定は変更しない。
- Shell初期化に失敗した場合に従来Qt経路へ戻る仕組みは維持する。

## INIでの従来方式への切り戻し

ユーザー用の `%LOCALAPPDATA%\FRBLaunch\state.ini` を開き、`[General]` 節に以下を設定する。

```ini
[General]
files_list_explorer_drag=false
```

- `true` （または項目なし）: **Windows Shell方式（標準）**
- `false`: **従来Qt URL方式（互換性用）**
- 設定を変更したら、トレイも含めLaunchを**完全終了 → 再起動**。
- **既存state.iniの内容は自動で書き換えない**。項目が無い既存ユーザーも新標準で起動する。
- `defaults/state.ini` は新規ユーザーの初回シードだけを規定し、既存のユーザーデータは変更しない。

## 影響範囲

設定は **Files Listだけ**。その他の外部ドラッグは従来方式。試験版の `src/native_shell_drag.py` が必要（この差分ZIPに含む）。Windows Shell方式で他アプリのD&D結果が変わる可能性は残るため、普段使いの主要なドロップ先でも確認する。問題があれば上記のINIで切り戻し。

## 適用方法

- 前提: `launch_app_20261121_105705.zip` + `FRBLaunch_ExplorerShellDnD_Trial_20261121_diff.zip` の適用済み状態。
- ZIPをLaunchルートに上書きし、Launchを完全終了して起動し直す。
- Windows実機動作の再確認はこれから。PySide6未導入の検証環境ではGUI操作の自動検証不可。
