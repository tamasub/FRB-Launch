# FRB Commander 初号機案 — Export-DiffToJson

対象: ユーザー提供 `Export-DiffToJson.ps1` (MetaDiff v0.1.3-draft)

## 中心思想

- Launch: やりたい処理を見つけるための検索・階層
- Commander: 処理のパラメータを連続選択する操作エンジン
- ViewDef: 選択候補、次に選択可能な項目、条件付き表示、実行引数への結び付け
- パンくず: ファイル階層ではなく、選択済み条件への再編集入口
- スクリプト: 対話メニューを持たず、引数を受け取り処理する

## 経路

| 最初の選択    | 次にすること                | PowerShellの引数                                            |
| -------- | --------------------- | -------------------------------------------------------- |
| 未ステージ差分  | 実行プレビューへ              | 省略可（`-Mode WorkingTree`）                                 |
| ステージ済み差分 | 実行プレビューへ              | `-Mode Staged`                                           |
| HEADとの差分 | 実行プレビューへ              | `-Mode Head`                                             |
| コミット範囲   | `Range` を入力           | `-Range "main..HEAD"` 等                                  |
| 2ファイル比較  | `FromFile` → `ToFile` | `-Mode FilePair -FromFile "old.json" -ToFile "new.json"` |

上記の最初の選択は「フォルダー階層」ではなく、入力したい実行モードを定めるための選択です。候補一覧の絞り込み、Enterで確定、次の候補の即時表示、パンくずから再選択を共通エンジンが提供します。

## 詳細設定

- `Unified` 既定 3
- `MaxPatchChars` 既定 60000（ファイルごと）
- `NoPatch` 既定 false
- `OutputPath` 既定 `wwwroot/diff/DiffToJson_current.json`（FRBStudio_Appルート基準）

## 実装前に決めること

1. `.viewdef` の正式スキーマと条件式の表現
2. 候補生成方法（固定値／履歴／ファイル選択／Git参照の取得）
3. キーボードの入力契約（`/`、矢印、Enter、Escape、再編集）
4. Runnerの実行契約：引数配列として渡し、実行プレビュー・確認・ログを持つ
5. 不正な定義や任意コードの実行を防ぐ信頼境界

**注意:** 同梱の `.viewdef` は操作仕様のたたき台で、現時点のLaunch/Commanderが読み込めるとは限りません。`Export-DiffToJson.ps1` は変更していません。
