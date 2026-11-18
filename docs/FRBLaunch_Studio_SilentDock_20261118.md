# FRB Launch / Studio: 第3列への静かな収容（2026-11-18）

## 対象

- Launch 基準: `launch_app_20261118_184303.zip`
- Studio 基準: `FRBStudio_App20261118_184326.zip`
- Launch → Files List の JSON ダブルクリック → 第3列へ Studio NativeShell 収容

## 症状

Studio NativeShell が本来の 1500×950 ウィンドウとして一瞬デスクトップに表示され、その後 Qt 第3列へ移動する。原因は Launch が「デスクトップ上に見える通常ウィンドウ」を検出してから `SetParent` していたこと。

## 設計

1. `--launch-preview` で起動した NativeShell **だけ** 最初は `Opacity=0`、タスクバー非表示。単独 Studio のスプラッシュ／通常起動には手を触れない。
2. Launch は自分で起動した PID の **正確な NativeShell タイトル**だけを探す。プレビューに限り透過・タスクバー非表示状態でも認識する。
3. 第3列ホストへの `SetParent` とサイズ調整が成功してから、既存の非公開セッションパイプに `@FRB_LAUNCH_DOCKED@` を送信する。UI スレッドでは待機しない。
4. NativeShell は実際に `WS_CHILD`／親 HWND を確認してから不透明化し、ACK を返す。再アクティベート／タスクバー切替はしない。
5. 収容確認前は Studio 外出しを一時的に無効化し、完了後に復帰。
6. 失敗時に透明なまま永続化しないよう、Studio 側に 45 秒の安全復帰処理を置く。既に第3列へ収容されていればタスクバー変更や再親子化を避ける。
7. 明示的な外出し、Launch の異常終了、未保存データの保持処理は引き続き既存契約を使う。

## 適用

Launch 側差分ZIPを Launch ルートへ上書き。Studio 側差分ZIPを Studio ルートへ上書き。**Studio 側は必ず NativeShell の再ビルドが必要**。Launch が参照する `NativeShell/_publish/FRBStudio.NativeShell.exe` へ成果物が反映されていることを確認する。

Studio ルートで:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build/Build-NativeShell.ps1
```

Launch / Studio を終了してから適用・再起動すること。両方を更新せず Launch だけ更新した場合は、従来 Studio と専用通信が合わず、収容確認エラーになる可能性がある。

## テスト

- Launch Python 検証: 85件PASS（既存関連＋新規）
- Studio Node 静的契約: 10件PASS（既存関連＋新規）
- Python `py_compile`: PASS
- Windows 実機での NativeShell ビルド・スクリーン描画・起動／収容／外出し: **未実施**

### Windows で確認したいこと

1. JSON をダブルクリックした直後、デスクトップに大きな Studio ウィンドウが出ず、第3列の中だけで表示される
2. 第3列から別の JSON へ切り替えても同じプロセスを使い、未保存確認は従来通り
3. Studio 外出しで独立ウィンドウに復帰でき、編集中の内容が保持される
4. 単独 Studio の起動は従来通り
5. 失敗時は第3列に理由が出て、透明なプロセスが操作不能のまま残らない

**注意:** 実機検証前の試作。問題が出たら両方のソースを元ZIPへ戻し、NativeShell を再ビルドする。
