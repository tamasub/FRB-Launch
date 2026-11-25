# FRB Launch — Python 3.15.2 開発環境移行

対象: launch_app_20261125_191757.zip / Windows x64 / 2026-11-25

## 目的・変更範囲

Python 3.15.2 (標準のGILあり、非free-threaded、x64) でソース実行とEXEビルドを行える構成へ移行する。3.15系のパッチ更新は許容する。既存の3.10〜3.14標準64bit環境向けの依存バージョンは維持。新規venvの標準を3.15へ変更した。アプリ本体、メニュー/Commander JSON、UserData、アプリのバージョン番号は変更しない。

| パッケージ | Python 3.10〜3.14 | Python 3.15 |
|---|---|---|
| PySide6 | 6.10.1 | 6.12.0 |
| PyInstaller | 6.17.0 | 6.22.3 |
| PySide6-WebEngine | PySide6内 | 6.12.0.140 (明示指定) |
| tzdata | 2025.2 | 2025.2 |

PySide6 6.12ではWebEngineのwheelが分離されたため明示する。PySide6本体の依存としても導入される。Windows ARM64ネイティブ版ではWebEngineの実体を含むwheelが確認できないため、今回の3.15移行対象はx64に限定。

## PC側の作業手順

1. Launchをトレイから終了。Updaterやソース起動中のPython、venvを使用するターミナル等も終了する。従来のPython 3.14は、新環境の動作確認が終わるまでアンインストールしない（会社の管理方針が許す場合）。
2. `backup_frb_launch_config_log.bat` などで設定をバックアップする。既存 `dist/FRBLaunch` の**フォルダー全体**を別の場所にコピーして保管する。ビルド中にdistは再作成され、venvのロールバックだけではdistは復元されない。
3. https://www.python.org/downloads/release/python-3152/ から Windows x64の標準Pythonを導入する。Python install managerを使う場合はインストール後に新しいコマンドプロンプトを開いて `pymanager install 3.15` を実行する。会社では許可されたインストール方法を使う。3.15tではなく3.15を選ぶ。
4. 新しいコマンドプロンプトで以下を確認する。

```bat
py -0p
py -3.15 --version
py -3.15 -c "import sys,struct,sysconfig,platform; print(sys.executable,struct.calcsize('P')*8,platform.machine(),sysconfig.get_config_var('Py_GIL_DISABLED'))"
```

期待: Python 3.15.2 (または新しい3.15.x)、64、AMD64、最後の値が0またはNone。旧Python Launcherとinstall managerの競合時は `where py`、`pymanager list` を確認し、公式手順を参照。Pythonインストール後も、既存の.venvは自動では切り替わらない。

5. 差分ZIPをLaunchソースフォルダーに上書き展開する（ユーザー設定は含まれない）。`_build_windows.bat`、`requirements.txt` があるフォルダーで次を実行。

```bat
update_python_env.bat --no-build
```

旧 `.venv` を `.venv_backup_YYYYMMDD_HHMMSS` へ退避し、新しい `.venv` を作成する。requirementsのインストール、pip check、Qt/WebEngine/PyInstallerの読み込み確認を実行。移行時に失敗した場合は旧venvを復元する（旧Python本体が存在することが必要）。

6. 新しいvenvを確認して、ソースから起動する。

```bat
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe src\python_build_environment.py --migration --dependencies
.venv\Scripts\python.exe src\app.py
```

7. ソース動作確認後、Launchを終了し、EXEを作成する。

```bat
_build_windows.bat
```

既存の契約チェック、テンプレートの読み取り検証、pip check、依存パッケージのバージョン/読み込み、ネイティブGUI描画確認をすべて通過するまで旧distを削除しない。生成された `dist\FRBLaunch\FRBLaunch.exe` を起動し、第3列ブラウザー、設定画面、Exp、List、KeyboardEx、Commander、終了/再起動を確認する。今回の移行は会社の認証やCommander設定の不具合自体を直すものではない。

8. 配布・更新用バイナリが必要な場合は、同じvenvで以下を実行して作り直す。まだ配布・アップロードしない。

```bat
_build_updater_windows.bat
_build_updater_helper_windows.bat
```

9. 一括実行なら `update_python_env.bat` (引数なし) で環境移行とLaunch EXE再ビルドを行える。ただし今回は切り分けのため --no-build を推奨する。旧venvと旧distの退避物は実機確認後に手動削除する。旧venvをsource ZIPやGitへ含めない対策を追加済み。

## エラー時

- `py -3.15` が見つからない: Python install manager/launcherやインストール済みruntimeを確認。
- pipが失敗: 会社のプロキシ、許可されたパッケージリポジトリ、バージョン制限を確認。証明書検証を無効化しない。
- PyInstaller 6.22.3: 公式changelogの次期リリース項目に、標準Python 3.15の一部Windowsインストールで `abi3t-compat/python3t.dll` の収集を修正する記述がある。実際にエラーが出た場合はログを確認し、正式リリース済みの修正版を検討する。現時点で未リリースの版へは固定しない。
- 旧venvが復元されても旧distは自動復元しない。必要ならバックアップしたフォルダーを戻す。venvを戻すときは新venvを退避してから、旧venvのディレクトリー名を `.venv` に戻す。旧Python本体が必要。

## 検証の範囲

この差分はLinux/Python 3.13.5上で静的検証、非GUI回帰テスト、契約チェックを行った。Windows/Python 3.15.2での依存インストール、ネイティブGUI、EXE作成・起動、配布物検証は未実施。

関連する旧テスト `tests/test_launch_home.py` 5件は、添付ZIPに `config/frb_launch_data.json` が存在しないためfixtureの準備時に失敗。旧設定ファイルを勝手に復元したり生成したりせず、今回の変更範囲外とした。

## 参照

- https://www.python.org/downloads/release/python-3152/
- https://docs.python.org/ja/3/using/windows.html
- https://pypi.org/project/PySide6/6.12.0/
- https://pypi.org/project/PySide6-WebEngine/6.12.0.140/
- https://pypi.org/project/pyinstaller/6.22.3/
- https://www.pyinstaller.org/en/latest/CHANGES.html
- https://www.qt.io/blog/qt-for-python-release-6.12-is-here
