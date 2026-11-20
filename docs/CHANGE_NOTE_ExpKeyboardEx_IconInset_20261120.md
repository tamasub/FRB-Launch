# FRB Launch — Exp Keyboard Ex アイコン左余白調整（2026-11-20）

## 対象と目的

正本: `launch_app_20261120_203906.zip`

Exp Keyboard Ex のアイコンだけを少し右に寄せ、メニュー外枠からアイコンまでの余白を増やす。既存の Files Exp/List 右クリックメニューとのバランスを考慮し、大きく動かさず **6px** の試作値を採用。

## 修正内容

`src/launch_appearance.py` の `SLASH_EXP_ICON_INSET_PX = 6` を追加。

- 短いメニュー（`QMenu`）：`QMenu#slashExpNavigationMenu::icon` の相対位置を右へ6px
- 長いメニュー（`QTreeWidget`）：`QTreeWidget#slashExpFixedScrollList::icon` も同じく右へ6px
- アイコンを自前で描画しない。文字・矢印・行の選択範囲・検索ボックスは元のQt描画を維持する。
- ほかのコンテキストメニューの共通テーマ／余白は変更しない。
- 背景色・角丸・枠線・影・メニュー表示位置・高さ・`/` 操作に変更なし。

## 調整方法

`src/launch_appearance.py` の定数だけ変更可能。例：`SLASH_EXP_ICON_INSET_PX = 4`（控えめ）、`8`（広め）。

Qtでは `QMenu::item` の `padding-left` 変更が、アイコン位置を移動させない場合がある。今回は専用の `::icon` セレクターで調整する。

## 検証

- 関連テスト71件 PASS
- 広めのテスト 102 PASS / 1 FAIL。FAIL は未変更の Obsidian 外部エディタ連携テストに由来する旧期待値。
- Windows 11 実画面のアイコン位置は未検証。特に長い一覧（スクロール表示）と通常メニュー双方で確認する。

## 変更ファイル

- `src/launch_appearance.py`
- `tests/test_slash_exp_icon_inset_20261120.py`（新規）
- `docs/CHANGE_NOTE_ExpKeyboardEx_IconInset_20261120.md`（新規）
