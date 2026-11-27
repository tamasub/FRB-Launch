# FRB Commander ViewDef 作成ガイド v0.1 — AI協働用

- 対象: FRB Launch / FRB Commander（バッチコマンダー）
- ViewDef仕様バージョン: `frb_commander_viewdef_v0.1`
- 基準日: 2026-11-27（folder_path 追加。v0.1互換拡張）
- 正本: `src/commander/viewdef.py`、`src/commander/window.py`、`src/commander/launch_adapter.py`
- 同梱スキーマ: `frb_commander_viewdef_schema_v0_1.json`（JSON Schema Draft 2020-12）
- 配置: `FRB_Launch/defs/commander/`。この2ファイルは作成用の参照資料であり、Commander起動時には不要。

## 1. AIへの依頼方法

このガイドとスキーマ、対象の実際の `.ps1`（必要ならその依存スクリプト・README）、人間が選択したい実行パターンを渡す。

以下はそのまま利用できる依頼文。

> 添付のPowerShellスクリプト用に、FRB Commander v0.1の `.viewdef` を作成してください。添付JSON Schemaおよび作成ガイドを遵守してください。実際のparamブロック、ValidateSet、既定値、必須条件、ParameterSet、実行時の分岐・副作用を確認し、ユーザーが選択したい実行パターンを定義してください。スクリプト本体は変更しないでください。未対応機能や確認不能な点は推測で補わず報告してください。成果物は対象PS1と同じベース名のUTF-8 JSON（拡張子 `.viewdef`）とし、各経路の選択値・期待引数配列・依存環境・副作用を別途簡潔に示してください。JSON Schema検証と本ガイドの意味的検証を行い、検証できなかった項目を明記してください。PS1の実行は依頼されない限り行わないでください。

## 2. 責務と配置

Commanderは人間の選択からPowerShell実行コマンドを組み立て、確認後に発行するUIである。ViewDefは選択経路と引数の対応を宣言する。PS1の業務処理、Node.js・Git等の探索や導入、ファイルの作成、上書き可否、エラー処理はPS1自身の責務。CommanderやViewDefがPS1の依存環境を提供するわけではない。

PS1とViewDefはLaunchの管理外にあってもよい。事前登録は不要。ただし、ファイル／フォルダー選択UIを利用する場合はLaunch内でKeyboard ExのFiles Expが利用できる必要がある。

```text
FRB_Launch/
  defs/commander/
    frb_commander_viewdef_schema_v0_1.json
    frb_commander_viewdef_authoring_guide_v0_1.md

D:/Work/MyTools/                  ← 任意の配置先
  Sample.ps1
  Sample.viewdef                  ← 実行用定義
  （PS1自身が必要とする依存ファイル）
```

- `.ps1` と同じフォルダー・同じベース名の `.viewdef` を置く。`Sample.viewdef.json` ではない。
- `script.file` は選択したPS1のファイル名のみ。絶対パス、相対ディレクトリ、別スクリプトは禁止。実装では大文字小文字を区別せず照合するが、同じ表記を推奨。
- JSONはUTF-8（BOMなし推奨。読み込みはBOM付きにも対応）。コメント・末尾カンマ禁止。日本語は可読な文字で記述し、不要なUnicodeエスケープを使用しない。
- `$schema` は実行用ViewDefに追加しない。この作成用スキーマは外部から検証に使用する。PS1とViewDefだけで持ち運べる状態を維持する。
- LaunchのFiles ListでPS1を右クリックし「FRB Commanderで実行」。

## 3. 最小構造と項目定義

以下は架空の `Sample.ps1` が `-Mode Preview` / `-Mode Convert` を受け付ける場合の例。実際のパラメーターは対象PS1で確認すること。

```json
{
  "schema_version": "frb_commander_viewdef_v0.1",
  "view_type": "frb_commander",
  "title": "設定の変換",
  "description": "診断と変換の選択",
  "script": { "file": "Sample.ps1" },
  "steps": [
    {
      "id": "source",
      "label": "実行方法",
      "input": "single_choice",
      "required": true,
      "choices": [
        { "value": "preview", "label": "診断のみ", "hint": "書き込まない", "args": ["-Mode", "Preview"] },
        { "value": "convert", "label": "変換", "args": ["-Mode", "Convert"] }
      ]
    }
  ]
}
```

| 項目 | 仕様 |
|---|---|
| `schema_version` | 固定値 `frb_commander_viewdef_v0.1` |
| `view_type` | 固定値 `frb_commander` |
| `title` | 必須。ウィンドウタイトル等に表示 |
| `description` | 任意。説明用。現行UIでは表示しない |
| `script.file` | 必須。同名PS1のファイル名 |
| `steps` | 必須。1件以上。配列順で選択項目を表示 |
| `steps[0]` | `id: source`、`input: single_choice` 固定。条件付き非表示にしない |
| `step.id` | 一意。`[a-z][a-z0-9_]*` |
| `step.label` | 人間向け表示名 |
| `required` | 省略またはtrue。現行GUIは表示される全項目の非空入力を要求する |
| `choices[].value` | 同一候補一覧で一意の内部文字列。引数そのものとは限らない |
| `choices[].label` | 人間向け候補名 |
| `choices[].hint` | 任意の文字列。候補検索・表示に使用 |
| `source.choices[].args` | 必須。選択した経路で渡す引数配列。引数なしなら `[]` |

### 入力タイプ（4種類のみ）

| input | 意味 | 追加項目 |
|---|---|---|
| `single_choice` | 固定候補から1件選択 | `choices`（空配列不可） |
| `text` | 1行の文字列入力 | なし。前後空白はUIで除去。空入力不可 |
| `file_path` | Keyboard Exで既存ファイルを1件選択 | `selector` 必須 |
| `folder_path` | Keyboard Exで既存フォルダーを1件選択 | `selector` 必須 |

後続の `single_choice` には `args` を置かない。`value` が文字列としてsourceの引数テンプレートに渡る。例えば候補valueを `JSON` / `CSV` とし、source側のargsに `"-Format", "${format}"` を記述する。表示名は日本語でよい。

### 条件付き表示

```json
"visible_when": { "source": "file_pair" }
```

1件のキーと文字列の値のみ。指定されたstepの選択値と完全一致したときに表示する。未選択なら非表示。複数条件、AND/OR、比較式、配列条件、任意コードの実行には対応していない。

作成時は `source` または先行するstepのみに依存させ、対象が選択可能であることを確認する。`source` を変更すると後続選択値が消える。一方、一般の後続step変更時には依存値が自動消去されない（`from_file` 変更時の `to_file` 消去のみ特別実装）。複雑な分岐は避け、原則sourceによる経路分離を用いる。非表示の値が残っていることを前提にしてはならない。

### ファイル選択

```json
"selector": {
  "type": "keyboard_ex.file",
  "initial_location": { "type": "workspace_root" }
}
```

| initial_location.type | 意味 |
|---|---|
| `workspace_root` | 選択PS1を含む登録済みFilesルートのうち最も広いルート。なければPS1の親フォルダー |
| `script_dir` | PS1があるフォルダー |
| `parent_of` | `selection` で指定した先行ファイル選択の親フォルダー |

`parent_of` の例: `{"type":"parent_of","selection":"from_file"}`。参照するstepは先行する `file_path` とし、その経路で必ず選択済みになるよう定義する。

ファイルは実行されず、パスだけが返る。引数生成時にも実在ファイルか確認される。複数ファイル／フォルダー選択、まだ存在しない出力ファイルの選択、拡張子フィルターは現行ViewDefの機能ではない。出力パスを入力させるなら `text` を検討し、パスの妥当性・上書き等はPS1側で検証する。

### フォルダー選択（2026-11-27追加）

```json
{
  "id": "root",
  "label": "対象フォルダー",
  "input": "folder_path",
  "selector": {
    "type": "keyboard_ex.folder",
    "initial_location": { "type": "workspace_root" }
  }
}
```

sourceのargsに `"-Root", "${root}"` を指定する（PS1が実際に -Root を受け付ける場合）。初期位置はファイル選択と同じ `workspace_root` / `script_dir` / `parent_of`（先行するfile_pathの親）。フォルダーのみ表示し、Enterで選択、→で子階層、←で親列、Escで取消。各列の先頭「（このフォルダーを選択）」で現在のフォルダーを確定できるため空フォルダーも選択可。マウスはフォルダー行クリックで子列へ、先頭行クリックで確定。LaunchのFiles Listを移動せず、パスだけを返す。引数生成時に実在ディレクトリを再確認する。初期位置の外側への移動は未対応。従来のfile_pathの動作は変更しない。

## 4. 引数生成の契約

選択された `source` の候補に定義した `args` だけが使われる。後続のstepは入力値を供給する。`args` は **1要素=1引数** であり、シェル文字列ではない。

```json
["-Mode", "FilePair", "-FromFile", "${from_file}", "-ToFile", "${to_file}"]
```

- `${step_id}` は引数全体としてのみ使用可能。`"-Path=${path}"` や `"prefix/${path}"` のような部分置換は禁止。
- 固定値や選択値に空白が含まれていても、引数全体を追加の引用符で囲わない。JSONの文字列エスケープだけ適用する。
- `-Mode` と `FilePair` は別要素にする。PS1に存在しないパラメーターを推測して追加しない。
- `switch` は必要なsource経路に固定トークンで追加し、不要な経路では省略する。任意入力の有無によるargsの動的追加・削除はできない。
- PS1の既定値を利用したい場合は引数自体をそのsource経路から省略する。
- 引数値を参照するstepは、そのsource経路で必ず表示・入力されるようにする。現行実装は非表示参照や循環依存を完全には拒否しないため、作成時に確認必須。

実行時のコマンド仕様（ViewDefで変更できない）:

```text
program: powershell.exe
argv: [-NoProfile, -ExecutionPolicy, Bypass, -File, <PS1の絶対パス>, ...args]
working_directory: PS1の親フォルダー
```

実行はQProcessの引数配列で行う。コマンドコピーは同じコマンド仕様からPowerShell用 `Start-Process` 形式を生成する。コピーは実行しない。実行時は共通確認応答で明示的にYesを選択した場合のみPS1を起動する。確認メッセージの文面はViewDefで変更できない。PS1の副作用や安全性をViewDefが保証するわけではない。

## 5. 実例：Git差分・2ファイル比較

現行の実行用 `examples/commander/Export-DiffToJson.viewdef` から2ファイル比較経路を抜き出した例。対象PS1本体はこのLaunchソースZIPに含まれていないため、実際のPS1のparam確認は別途必要。

```json
{
  "schema_version": "frb_commander_viewdef_v0.1",
  "view_type": "frb_commander",
  "title": "Git差分をJSON出力",
  "script": { "file": "Export-DiffToJson.ps1" },
  "steps": [
    {
      "id": "source",
      "label": "比較方法",
      "input": "single_choice",
      "choices": [
        { "value": "working_tree", "label": "未ステージ差分", "args": [] },
        { "value": "commit_range", "label": "コミット範囲", "args": ["-Range", "${range}"] },
        { "value": "file_pair", "label": "2ファイル比較", "args": ["-Mode", "FilePair", "-FromFile", "${from_file}", "-ToFile", "${to_file}"] }
      ]
    },
    { "id": "range", "label": "コミット範囲", "input": "text", "visible_when": { "source": "commit_range" } },
    {
      "id": "from_file", "label": "比較元", "input": "file_path",
      "visible_when": { "source": "file_pair" },
      "selector": { "type": "keyboard_ex.file", "initial_location": { "type": "workspace_root" } }
    },
    {
      "id": "to_file", "label": "比較先", "input": "file_path",
      "visible_when": { "source": "file_pair" },
      "selector": { "type": "keyboard_ex.file", "initial_location": { "type": "parent_of", "selection": "from_file" } }
    }
  ]
}
```

期待引数（共通prefixより後）:

| 経路・入力 | 期待値 |
|---|---|
| working_tree | `[]` |
| commit_range / `main..HEAD` | `["-Range", "main..HEAD"]` |
| file_pair / 実在する2ファイル | `["-Mode", "FilePair", "-FromFile", "D:/Work/比較 元.json", "-ToFile", "D:/Work/比較 先.json"]` |

パスは説明用の例。実行時はKeyboard Exが返す実在パスを使用する。

## 6. 未対応機能と禁止事項

現在のv0.1では、次の機能を作成してはならない。

- `.bat` / `.cmd` / `.py` / `.exe` を直接実行する定義、任意runner指定、作業ディレクトリ変更。
- `text_with_history`、`integer`、`boolean`、`multi_choice`、`optional_group` 等の架空input。
- `default` による初期選択、`required:false` による入力省略、`command_bindings`、`run_confirmation`、`experience`、動的候補生成、任意の式評価。
- source以外の候補に引数を追加する方式。PS1本体を勝手に書き換える方式。

`tools/FRB_Commander/FRB_Commander_Git_ViewDef_Concept_20261123/Export-DiffToJson.viewdef` は初期構想（`v0.1-draft`）で実行用ではない。これを仕様として使わない。Studioの汎用編集用ViewDefとも別仕様である。

## 7. AIの納品前チェック（スキーマ検証 + 意味的検証）

JSON Schemaは型・必須項目・許可キー・入力タイプ・初期位置・引数テンプレートの書式を検証する。現行実装が未知のキーを無視する場合でも、この作成用スキーマは未知のキーを拒否する。空白だけの値、`required:false`、sourceの条件付き表示等も作成禁止とする。実行時validatorそのものを置き換えるものではない。

以下はJSON Schemaだけでは保証できないので別途確認する。

- [ ] `.ps1` と `.viewdef` の同名・同一フォルダー配置、`script.file` の一致。
- [ ] step IDの重複なし、各choicesのvalue重複なし。
- [ ] visible_whenの参照先が先行stepとして実在し、指定値が選択可能。循環・自己依存なし。
- [ ] parent_ofの参照先が先行するfile_pathであり、同じ経路で入力される。
- [ ] 各source経路のプレースホルダーが実在し、参照先がその経路で表示され入力される。
- [ ] 全経路で実際のPS1のparam、型、必須条件、ValidateSet、ParameterSet、既定値と引数配列が整合する。
- [ ] 不要な引数、選択しても効果のない項目、空入力前提の項目がない。
- [ ] 日本語、空白、引用符を含む値は引数単位で保持される。PS1の受け取り側も検証する。
- [ ] PS1の外部依存と上書き・削除などの副作用が人間に説明されている。
- [ ] 各source経路のExpected argvを提示し、実行せずに検証できる範囲を確認する。

既存のPython実装が利用できる開発環境なら、`src/commander/viewdef.py` の `read_viewdef` / `visible_steps` / `build_command` を用い、PS1を実行せず引数・作業フォルダーを検証できる。JSON Schema検証にはDraft 2020-12対応validatorを使用する（例: Python jsonschema）。これらはAIの作成時の検証手段であり、利用者PCへの追加インストールを要求しない。

- [ ] folder_path は keyboard_ex.folder、file_path は keyboard_ex.file。既存パスの種類を検証する。

## 8. 資料の管理

- `defs/commander/` に本ガイドとスキーマを一組で置く。既存 `defs/launch/`（Launch/StudioのViewDef）と分ける。
- 配布処理 `scripts/build_release_package.py` は `defs/` 配下を収集するため、この配置はPortable版とUpdater版への同梱に適する。個人スクリプトや個人パスをここに登録しない。
- 実行用 `.viewdef` は各PS1の隣に置く。共通スキーマやガイドをコピーする必要はない。
- Commanderの入力タイプ・引数生成規則が変わった場合、スキーマ・本ガイド・実装テストを併せて見直す。

基準資料: `launch_app_20261125_213438.zip` に `FRBLaunch_Commander_HorizontalNavigation_diff_20261125.zip` を重ねたソース。`src/commander/viewdef.py`、`src/commander/window.py`、`src/commander/launch_adapter.py`、`examples/commander/Export-DiffToJson.viewdef`、`tools/FRB_Commander/LaunchConfigMigration/Migrate-LaunchConfig.viewdef`、`tests/test_commander_viewdef_v01.py` を参照。

### 初版作成時の検証記録

- JSON Schema Draft 2020-12 のメタスキーマ検証: PASS。
- 既存実行用ViewDef 2件 + 本ガイドの完全な定義例2件: スキーマ検証・現行Python validatorともPASS。
- 上記4定義の合計12経路: 一時PS1・一時ファイルを使い、引数配列と作業フォルダーの一致を確認。日本語・空白を含むファイルパスも使用。PS1は実行していない。
- 不正な定義11パターンと初期構想版1件: スキーマによる拒否を確認。
- Windows上の実行・GUI動作および実際のGit差分スクリプトのparam照合は未検証。スキーマとガイドの追加のみであり、実行時コードは変更していない。
