# FRB Launch 起動不能修正 — Ctrl+H 検索履歴初期化ガード

基準：`launch_app_20261116_205359.zip`（ユーザー提供の最新一式）

## 症状

`ExpandedLauncherView.__init__` の中で Files List 検索履歴ボタンを作成している途中に、
アプリケーション全体へ登録済みの `eventFilter` が先に動き、
未生成の `self.middle_search_history_menu` を参照して `AttributeError` により起動が中断。
この例外がエラーダイアログ表示中にも連鎖していた。

## 原因

ボタン生成直後からグローバル `eventFilter` が `handle_middle_search_history_key` を呼べる構造になっている一方、
同ハンドラーはメニューの生成完了を無条件に前提としていた。
旧テストは生成完了したオブジェクトだけでキー操作を検証しており、初期化途中を未検証だった。

## 修正箇所

- `src/expanded_view.py`
  - `eventFilter` はボタン・メニューの双方が生成済みのときだけキーアダプターを呼ぶ。
  - `handle_middle_search_history_key` はキーイベントを先に確認し、未生成のボタン／メニューを `getattr` で安全に扱う。
  - `focus_middle_search_history` は未初期化状態ならフォーカスを移さず戻る。
  - キーワードアクションリストをメニューのイベントフィルター有効化前に初期化。
- `tests/test_launch_20261116_history_startup_guard.py`（追加）
  - メニュー生成前、ボタン生成前、通常操作時の振る舞い、イベントフィルターの防御を検証。
- `tests/test_launch_20261116_ctrl_h_and_chevron.py`
  - 既存の Ctrl+H テストに、生成完了したメニューを明示的に与えて前提条件を正しく設定。

## 適用

同梱の `src/` と `tests/` を、FRB Launch プロジェクトの同じ相対パスへ上書きしてください。
**ユーザー設定 JSON は変更していません。**

## 確認

1. FRB Launch がエラーなく起動する。
2. `Ctrl+H` → `↓`（履歴を開く）→ `↓`（項目選択）→ `Enter`（適用）ができる。
3. 通常のマウス・ぐりぐり操作、コンテキストメニュー、Ctrl+G に影響がない。

自動テスト：関連32件 PASS（PySide6 を必要としない既存テスト＋新規テスト）。
`python -m py_compile src/expanded_view.py` PASS。
本環境には PySide6 と Windows GUI がないため、Windows 実起動は未検証です。

参考：別の古い外観テスト `tests/test_header_blank_focus_20261025.py` が、
変更していない `src/launch_appearance.py` の CSS と期待値不一致で1件失敗。
この既存の不一致は今回の修正範囲外です。
