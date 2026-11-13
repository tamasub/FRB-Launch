# FRB Launch 0282 — FRB_Apps兄弟Studio自動検出

## 目的

物理移行直後の配置：

```text
F:\FRB_Apps\
├── FRB_Launch\
└── FRB_Studio\
```

これに対し、Launch設定JSONの `studio_root` は旧 `F:\FRB\tools\FRBStudio_App` を指したままなので、
「メニュー設定 (FRB Studio)」を押すと旧 `_publish` を探して失敗する。

## 対応

- `src/runtime_paths.py`：Launchホームの兄弟 `FRB_Studio` を検出対象へ追加。
  - `FRB_Launch/Studio`（従来のポータブル同梱形式）も保持。
  - まずNativeShell実行ファイルを検出。なければcsprojを持つソース版Studioを検出。
  - cwdを参照しない。設定JSONを自動書き換えしない。
- `src/app.py`：同じ検出結果が `studio_root` に反映され、メニュー設定・登録済みStudio起動・JSON/MDのStudioルーティングに適用される。
  - EXE未生成時は **新Studioのパス** と `cmd_compile_NativeShell.bat` 実行案内を表示。
- `src/launch_menu_registration.py`：Change Coreも兄弟 `FRB_Studio` のソースを優先検出する。
- 関連するPure Pythonテストを追加。

## 安全条件

- `config/frb_launch_data.json` を含むユーザー設定は **変更しない**。
- 旧フォルダーは復活させない。残っている古い絶対パスを新パスへ一括置換しない。
- StudioやLaunchの起動EXEはこの差分に含まれない（Windowsで再ビルドが必要）。
- `FRB_docsExcel` 等、研究・業務用のフォルダーは移動対象外。

## Windows実機の確認

1. `F:\FRB_Apps\FRB_Studio\NativeShell\_publish\FRBStudio.NativeShell.exe` が存在するか確認。
   - なければStudio側で `cmd_compile_NativeShell.bat` を実行する。
2. `F:\FRB_Apps\FRB_Launch` に差分を適用する。
3. 開発起動なら `_run_windows.bat`。EXE起動なら `_build_windows.bat` で再ビルド。
4. Launchの「メニュー設定 (FRB Studio)」をクリック。新Studioが起動することを確認。
5. LaunchのJSON登録・フォルダー追加などChange Coreを使う操作と、Studio管理JSON/MDの開き先を確認。
6. 設定JSONの古い固定パス（直接登録した実フォルダーなど）の整理は別工程として扱う。

## テストの限界

Pythonテストとソースの検証のみ。WindowsのNativeShell実起動・起動引数・フォーカス動作は未確認。
