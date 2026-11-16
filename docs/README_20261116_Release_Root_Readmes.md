# FRB Launch 配布ZIP：ルートREADME同梱対応（2026-11-16）

## 依頼

`_release_FRBLaunch_GUI.ps1` で配布媒体を作るとき、`F:\FRB_Apps\FRB_Launch` の直下にある `readme*.*` を同梱する。特に `README_Vector_v0.9.11.txt` を含める。

## 変更したファイル

- `scripts/build_release_package.py`：配布ファイルの共通収集処理 `collect_files()` に、Launchソース直下の `README` で始まるファイル名（大小文字区別なし）の追加収集を実装。
- `tests/test_release_root_readmes_20261116.py`：実際のテスト用の更新ZIPとポータブルZIPを生成して、内容と配置を検証。

GUI → `release_FRBLaunch_GitHub.ps1` → `scripts/release_github_pipeline.py` → `scripts/build_portable_distribution.py` → `scripts/build_release_package.py` の順で配布ファイルを作る。GUI本体の変更は不要。

## 同梱対象・配置

| 元ファイル（Launch直下） | 更新用ZIP | ポータブルZIP |
|---|---|---|
| `README.md` | `system/README.md` | `FRBLaunch/README.md` |
| `README_Vector_v0.9.11.txt` | `system/README_Vector_v0.9.11.txt` | `FRBLaunch/README_Vector_v0.9.11.txt` |

`ReadMe_INSTALL.TXT` など、同じ命名条件のファイルが増えれば次回から自動同梱。

**範囲**：ソース直下のみ。`docs/` 配下を無差別に取り込まない。既存の配布禁止条件（任意のZIP・ログ・シンボリックリンク等）は維持。元ファイルのバイトを変換せずコピー。

## 適用方法

1. この差分ZIPを `F:\FRB_Apps\FRB_Launch` に展開して上書きする。
2. `README.md` と `README_Vector_v0.9.11.txt` がソース直下にあることを確認する。
3. いつもどおり `_release_FRBLaunch_GUI.ps1` から新しいバージョンの配布を準備する。
4. **公開前に** 作成された `FRBLaunch_<version>_portable.zip` を開き、`FRBLaunch/README_Vector_v0.9.11.txt` を確認する。

**注意**：既存配布ZIPは安全のため上書きしない。既に同バージョンで配布準備済みなら、同じZIPを上書きせず、適切な新バージョンで準備すること。

## テスト

- リリース関連テスト29件 PASS（Linux側のPythonテスト）。
- テスト用の更新ZIP・ポータブルZIP双方へのREADME同梱とファイルバイト一致を確認。
- Windowsの実際のGUIから配布する最終確認は未実施。
