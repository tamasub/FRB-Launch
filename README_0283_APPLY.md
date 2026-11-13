# FRB Launch 0283 — GUIスモーク誤判定の切り分け

- 0282を適用した `F:\FRB_Apps\FRB_Launch` に差分ZIPを上書きしてください。
- 設定JSON、ユーザーデータ、アプリ本体の描画コードは変更していません。
- まず `.venv\Scripts\python.exe scripts\smoke_context_menu_native_gui.py` を実行。
- ExpとListがPASSなら `_build_windows.bat` を実行してください。
- FAILしたら `context_menu_smoke_failure_exp.png` と `context_menu_smoke_variant_exp.png` を確認してください。実描画の欠落が疑われるときにテストをスキップしないでください。
- 詳細：`docs/FRBLaunch_0283_ContextMenu_GUI_Smoke_20261112.md`。
