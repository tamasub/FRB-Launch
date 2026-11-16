# FRB Launch 2026-11-16 — 操作性5点修正（差分）

**入力基準**：`launch_app_20261116_201003.zip`。`config/`、`defaults/`、個人の履歴/登録データは変更しない。変更対象はPythonソース4点・既存テスト1点、新規テスト1点と本メモ。

## 操作契約

| # | 対象 | 変更後のExpected | 限定・維持する操作 |
|---|---|---|---|
| ① | Expのカレントフォルダー、ぐりぐりボタン右クリック | **登録済みのFilesルート本人**なら、実フォルダーメニュー末尾に `Launch Menu ▶` が現れる | 物理的な子フォルダー・一般のドライブにはLaunch登録編集項目を出さない。登録根拠は既存 `registered_root_identity`→`verified_registered_root` の二重検証。マウス右クリックと同じ入口へ。 |
| ② | Files **List** の `PageUp` | まだ先頭以外なら通常PageUp。すでに先頭行で再度PageUpなら、既存の `go_up(keep_middle_focus=True)` により親フォルダーへ移る | 仮想フォルダー・Files登録ルート等の論理境界は既存の保護を維持。編集中は発火させない。 |
| ③ | メイン検索欄の `↓` | 1回目で既存の検索履歴ポップアップを開き、2回目以降で履歴の選択行を移す | Enterで選択確定。入力は実行せず既存検索機能を使う。 |
| ④ | `Ctrl+G` | Files表示中、パンくず左端のフォルダー履歴（お気に入り）ボタンへフォーカス。1回目の `↓` で保存フォルダー一覧を開き、以後の `↑↓` で選択行移動。Enterでフォルダーへ遷移 | ③のキーワード検索履歴と④の**保存フォルダー一覧**は別データ。クリック履歴の書き換えなし。Tabのフォーカス順序に入れないためボタンはClickFocusに設定。 |
| ⑤ | Files **List** 行の `→` | 旧「フォルダー進入／ファイル実行」は廃止。**右クリックと同じコンテキストメニュー**を選択行に表示する | メニュー内は `↑↓` 移動・`→` サブメニューを開く・`←` 戻る/閉じる・`Enter` 実行・`Esc` 閉じる。Exp/Bookmark/Pageの→やListのEnterはそのまま。既存コンテキストメニューのQActionとぐりぐりRunnerを共用。 |

## 改修場所

- `src/app.py`：Expルートの認可付きメニュールート、List PageUp、List→、メイン検索↓、Ctrl+G。
- `src/expanded_view.py`：パンくずフォルダー履歴ボタンのキーボードフォーカス、一覧の矢印操作。
- `src/remote_context_wheel.py`：List→で開いたQt.Toolメニューに限り、既存 `RemoteContextWheel.command()` にキーを配送（メニューに別の選択状態は作らない）。
- `src/expanded_keyboard_model.py`：List→の純粋モデルを `context_menu` に改定。
- `tests/test_expanded_keyboard_20261024.py`：旧 List→ 契約のExpected改定。
- `tests/test_launch_20261116_five_keyboard_changes.py`：新仕様の6テスト。

## 検証

- `python -m compileall -q src/app.py src/expanded_view.py src/expanded_keyboard_model.py src/remote_context_wheel.py`：成功。
- `python -m pytest -q tests/test_launch_20261116_five_keyboard_changes.py tests/test_search_history.py tests/test_search_history_categories_20261029.py tests/test_directory_favorites_20261025.py tests/test_context_menu_json_separator_paste_20261025.py tests/test_frb_context_menu_owns_runner_20261112.py`：**38 passed**。
- この実行環境に `PySide6` とWindowsデスクトップはないため、**実画面・ぐりぐり実機操作は未実施**。上記6件はQt非依存の契約/Runner疑似操作テスト。

### Windowsでの受入確認

1. Expの**登録済みFilesルート**にカレントを合わせぐりぐり上で右クリック → `Launch Menu ▶` があり、子フォルダーでは出ない。
2. Listの先頭以外でPageUp → 通常のページスクロール。先頭行に来て再度PageUp → 親フォルダー。論理ルートを超えない。
3. メイン検索欄にカーソル → 1回目の↓で履歴を開き、2回目以降にハイライトが移動。Enter確定。
4. Files画面でCtrl+G → パンくず左端にフォーカス。↓で保存フォルダー一覧、さらに↓・↑でハイライト移動。Enterで遷移。
5. Listでファイル、フォルダー、Launch JSON仮想行、複数選択の各パターンで→ → 右クリックと同じメニュー。上下、子メニューの右/左、Enter、Escを確認。**List Enter**は従来のままフォルダーへ進む。

### 既存テストに関する注記

過去テストの一部は、現行構成とは異なる古いView/Root/Remote仕様のExpectedを保持しており、そのまま実行すると失敗する（例：`test_expanded_keyboard_20261024.py::test_focus_ring_forward_and_backward`、`test_directory_navigation_history_20261026.py::test_actual_files_first_column_handler_records_and_restores_directory`）。今回修正した5操作の回帰確認とは分けて扱う。
