# FRB Launch — Files List とんとんレーン：シングルクリックのフォルダー対象化

## 変更目的
Files List 左側の24px「～とんとん親帰り／カレントフォルダー操作 エリア～」で、
シングルクリックした際に、選択行を操作対象から外して現在のフォルダーを操作対象にする。

## 操作の契約
- **シングルクリック**: List 行の選択（緑背景）を解除し、従来の currentItem の緑輪郭線だけを残す。
  deliberate_blank_selection を事前設定し、非同期の選択修復で勝手に行選択が戻らないようにする。
  List のブランククリックと同じ `blank_clicked` を呼び、論理的な操作対象をカレントフォルダーへ移す。
- **ダブルクリック**: 従来通り親フォルダーへ移動する。
- **右クリック**: 従来通りフォルダー操作メニューを表示する。
- **そのほか**: カレントディレクトリ、Exp 展開状態、List の行記憶を変更しない。フォルダーの実データは変更しない。

## 適用
添付差分ZIPを `F:\FRB_Apps\FRB_Launch` にフォルダー構成ごと上書き解凍。
`_run_windows.bat` で動作を確認し、必要なタイミングで `_build_windows.bat` を実行。
ビルドを要求する変更は Launch 本体側の `src/expanded_view.py` のみ。

## テスト
- 新規: `tests/test_files_tonton_lane_single_click_20261115.py` 5件 PASS
- 既存関連: 操作関連24件 PASS（1件は旧版からの失敗のため除外）
- 構文: `python -m py_compile src/expanded_view.py` PASS
- 周辺の旧テスト4件は元ZIPでも同じ失敗を再現。今回の変更によるものではない。
- Windows 実GUIでの色・操作検証は未実施。
