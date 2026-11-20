# Exp Keyboard Ex — 操作メニュー枠線／幅／カレント行／日本語IME

Base: `launch_app_20261120_215139.zip`

## 修正点

1. **フォルダー／ファイル操作メニューの角丸と枠線**
   - 既存の FRBContextMenu（Exp/List共有の操作メニュー）のQt標準 QAction描画は維持。
   - 描画の最後にだけ、角丸の細い輪郭線を実線で描画。特に右辺・下辺を内側2.5pxへ配置して切り欠けを抑止。
   - ネイティブのドロップシャドウ抑制。色は既存の青白系を維持。
   - 過去の「アイコンや文字が消えた」事故のため、独自のアイコン／文字描画は禁止のまま。ビルドの静的チェックを枠線のみ許容する形に更新。

2. **Keyboard Ex経由の操作メニュー幅**
   - `SlashExpMenu` のうち `_context_source` がある操作専用列だけ、既存のFiles操作メニューに合わせて幅225px。
   - 探索用の第1階層（Files Listの名前列連動）と第2階層以降の幅には変更なし。
   - 長い操作名は既存の省略表示。完全名はツールチップと実アクションに保持。

3. **「（カレントフォルダー）」の背景**
   - 通常の短いQMenuでは、非選択時の背景をライト `#FAF7F4`（元の探索メニュー背景より少し白寄り）に変更。
   - 長い一覧でQTreeWidgetへ切替時も、同じ行背景を使用。
   - 選択中の既存ハイライト、操作メニューの青白、Files List本体の色は変更なし。

4. **検索欄の日本語IME**
   - Keyboard Exの各列の検索欄を、実際にQtフォーカスを持つ `QLineEdit` に変更。
   - 日本語IMEの変換中は矢印・Enter・Escapeをメニュー側で奪わず、変換確定後は従来どおり階層操作に使う。
   - `/` 開始時・子列へ右展開した時・左で親列へ戻った時、各列の検索欄へフォーカス。
   - 検索文字列による絞り込み、コンテキストアクションの実行対象、パンくずを起点とする階層解決は変更なし。

## 動作確認

- Python構文チェック PASS。
- 共通コンテキストメニュー契約チェック PASS。
- 関連テスト125件 PASS（11 subtestsもPASS）。

**未確認：** Windows 11 GUIでの実際の枠線描画／日本語IME変換／操作メニュー幅のピクセル評価。
実機では、短いメニュー・スクロールメニュー、ライト・ダーク、ひらがな変換→Enter確定→結果を選ぶEnter、`/`再押下を確認すること。

## 変更ファイル

- `src/app.py`
- `src/slash_exp_navigation.py`
- `scripts/check_context_menu_contract.py`
- `tests/test_slash_exp_three_menu_polish_20261120.py`
- `tests/test_frb_context_icon_equal_margins_20261112.py`
- `tests/test_slash_exp_menu_final_polish_20261120.py`（新規）
