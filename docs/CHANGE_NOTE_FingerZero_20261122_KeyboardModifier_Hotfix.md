# FRB Launch — 小指Zero キーイベント例外修正（2026-11-22）

## 現象

WindowsのFRB Launchを操作すると、`QWidget::eventFilter()` から、以下の例外がキー操作ごとに繰り返し発生する。

```text
File "src/finger_zero_keys.py", line 36, in finger_zero_action
    mods = int(modifiers)
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'KeyboardModifier'
```

## 原因と修正

PySide6から受け取る `Qt.KeyboardModifier` は、バージョンや列挙型の実装により `int(flag)` が失敗する。

- `src/finger_zero_keys.py` に `_qt_enum_int()` を追加。
- Pythonの整数はこれまでどおり処理し、Qtのenum/flagについては `.value` から整数値を取り出す。
- `key` / `modifiers` / `native_vk` に共通適用。
- 0=Enter、1=ダイアログTab、Windows Menu=既存`/`の割当は**変更なし**。
- `expanded_view.py` のイベントルーティングや、通常のキー・入力欄の動作は変更なし。

## テスト

- `tests/test_finger_zero_20261122.py` に、`int(flag)` が失敗する `enum.Flag` を使った回帰テストを追加。
- `.value`を持つキー列挙型、単独・複合修飾キーの判定を確認。
- 関連テスト68件 PASS（Linux環境・Qt非依存テスト）。
- Pythonの構文チェック PASS。

## 適用

本ZIPの `src/finger_zero_keys.py` を既存の `FRB_Launch/src/` に上書き。
必要に応じて `tests/` と `docs/` を追加・上書き。
**以前の『小指Zeroの逆襲』差分ZIPを適用済みであることが前提**。

## 注意

Linux環境にはPySide6がないため、Windows実機のキーイベントによるE2Eテストは未実施。
`sqlite_persistent_shared_dictionary_store.cc Invalid total_dict_size` は今回のPython例外とは別のChromium系ログであり、本修正の対象外。
