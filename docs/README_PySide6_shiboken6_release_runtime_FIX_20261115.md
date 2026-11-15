# FRB Launch: 配布版起動エラー（PySide6 / shiboken6）対策

## 現象

初回起動で `Failed to execute script 'app'` と表示され、`PySide6/__init__.py` の DLL ディレクトリ初期化で `shiboken6\libshiboken does not exist` などの ImportError が発生する。

## 今回の対策

1. `_build_windows.bat` でPyInstallerビルド直後、`scripts/ensure_qt_runtime_directories.py` を実行する。
2. `PySide6/QtCore*.pyd` と `shiboken6/Shiboken*.pyd` の存在を確認する（欠けていれば**停止**）。
3. PySide6が存在確認する `shiboken6/libshiboken` および `PySide6/libpyside` に、システム所有の小さなマーカーファイルを置く。
4. `scripts/build_release_package.py` で、これらのマーカーが存在することをリリース前に検証する。
5. ZIPの通常ファイル一覧とSHA-256の管理でマーカーを配布する。これにより「空フォルダーだけがZIP化時に消える」ケースを防ぐ。Updaterの検証形式やユーザー設定ファイルは変更しない。
6. PyInstaller 6以降の `_internal` と旧式のフラットレイアウトを双方検出する。

## 適用手順

1. Launchのソースルートへ差分ZIPを上書き展開（`src/app.py` には変更なし）。
2. `_build_windows.bat` を実行する。ビルド直後に `PySide6 runtime directories protected` が表示されることを確認。
3. **まず `dist/FRBLaunch/FRBLaunch.exe` を起動し、エラーなく画面が表示されるか確認する。**
4. 実行中のアプリを終了し、配布GUIの「準備・検証」で新規リリースZIPを生成する。
5. 新規の `*_portable.zip` をまっさらなフォルダーへ展開し、`FRBLaunch.exe` を起動して確認する。
6. 上記が通った後に限り、Publishへ進む。既存リリースや既存ユーザー設定は上書きしない。

### ローカル事前検査

```powershell
.venv\Scripts\python.exe scripts\ensure_qt_runtime_directories.py --dist dist\FRBLaunch --check
```

## 注意

- この修正で確実に防ぐのは「必要なQtディレクトリが空なので、ZIP化・更新時に失われる」ケース。今回の画像だけでは配布物の全ファイルを直接確認できないため、原因の最終確定にはWindows上で上記起動試験が必要。
- `shiboken6/Shiboken*.pyd` などのネイティブ拡張自体が無い場合は、マーカー作成で隠さずビルド停止する。
- すでに生成済みのZIPには遡及適用されない。**新しいバージョン番号で再ビルド・再ステージ**すること。
- 既存の `%LOCALAPPDATA%\FRBLaunch\state.ini` や `UserData` には触れない。
- 既存テストに加え、マーカーの配布ZIP同梱・Updater適用後の復元をユニットテストで確認する。

## テスト

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_pyside6_runtime_dirs_release_20261115.py -v
```
