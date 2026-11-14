FRB Launch + Studio + Updater 配布ZIP作成ツール (2026-11-14)
=======================================================

■ これは何？
古い _prepare_launch_portable.zip の後継です。
旧版の「データや設定を丸ごとコピー」「studio_rootを書き換える」処理を廃止し、
現在の FRB Updater Family v0.1 の System領域だけを収録します。

■ 適用
このZIPを「F:\FRB_Apps\FRB_Launch」に相対パスのまま上書き展開。
（既存の scripts/build_release_package.py は安全性修正を含むので上書き）
FRB Studio側のソースには変更不要です。

■ 事前ビルド（済んでいれば実行不要）
Launch : F:\FRB_Apps\FRB_Launch\_build_windows.bat
Updater: F:\FRB_Apps\FRB_Launch\_build_updater_windows.bat
Studio : F:\FRB_Apps\FRB_Studio\cmd_compile_NativeShell.bat

さらに、Node.jsのWindowsランタイム node.exe と公式の LICENSE が必要です。
Launch/dist/FRBLaunch/runtime/node/ または Studio/runtime/node/ にあれば利用。
なければインストール済みNode.jsを探します。見つからない時はエラー停止。
利用者PCでのNode.jsインストールは不要です。

■ 操作方法
「make_FRB_Launch_distribution.bat」をダブルクリック。
正式なバージョンを4つ入力します（統合版、Launch、Studio、Updater）。
番号は勝手に推定しません。いずれも x.y.z 形式です。
既存のOutput ZIPを上書きしないので、同名がある場合は移動してください。
旧名の make_FRB_Launch_Studio_bundle.bat や _release.bat からも実行可能。

既定の入力:
 Launch source  F:\FRB_Apps\FRB_Launch
 Studio source  F:\FRB_Apps\FRB_Studio (Launchの隣)
 生成先         F:\FRB_Apps\FRB_Release_Output

■ 出力例（バージョン 1.0.0 / Updater 0.1.0 を入力した例）
FRB_Release_Output/
  FRBLaunch_1.0.0_PRIVATE_REVIEW_portable.zip
  FRBLaunch_1.0.0_PRIVATE_REVIEW_update.zip
  FRBUpdater_0.1.0.exe
  SHA256_1.0.0.txt
  README_配布確認_1.0.0.txt

・portable.zip:
  解凍した FRBLaunch フォルダー内の FRBLaunch.exe を起動できる。
  Studio/、Node.js、System定義、初期Updater.exeを同梱。
  installed_release.jsonを初期配置。以後UpdaterがSystemファイルだけ更新。

・update.zip:
  release.json + system/ に全Systemファイルを格納。
  Updaterの適用対象。直接起動できるZIPではありません。
  Updater.exeは入れない（Updater更新は共通ヘルパー担当）。

・FRBUpdater_<version>.exe:
  共通ヘルパーの配布先に公開するUpdater EXEのコピー。
  URLを指定していない場合はfeed JSONを生成しない。

■ 公開承認の重要事項
最新の frb_launch_data.template.json には個人メニューとPC固有パスが残っています。
ユーザーの指示通り、テンプレートを勝手に改変していません。
初期状態では PRIVATE_REVIEW と明記した確認用ZIPしか作成しません。
外部公開用には defaults/frb_launch_data.template.json および
config/*.json を目視確認し、BATで APPROVED と入力してください。
これにより名前から PRIVATE_REVIEW が外れます。内容自体は変化しません。

■ 守る範囲
AppData / UserData / UserConfig / state.ini / Cookie / Studio研究文書は収録しません。
Studio/wwwroot/data/ と Studio/tools/.../output/ も除外します。
FRB Launchソース・Studioソースは一切変更しません。
ソースのzip_exportは別物で、配布ZIPに開発ソースを丸ごと入れません。
StudioのLaunch向けViewDefの正本は、Launch/defs/launch 側にあります。

■ URLを登録してFeedまで作る場合（公開先決定後）
現時点ではFeedの公開先URLを仮定しません。
公開URLが確定したら、.venv\Scripts\python.exe から
scripts/build_portable_distribution.py を直接実行して
--archive-url https://.../FRBLaunch_x.y.z_update.zip
--updater-url https://.../FRBUpdater_x.y.z.exe
を付けることで product_feed.json と updater_feed.json も作れます。
同じバージョンのZIPが既存なら上書きしないので別出力先で実行してください。
公開先の defs/update/update_sources.json には実在するFeed URLを設定する必要があります。

■ Windows実機テスト
生成物のWindows EXE/Qt/NativeShell起動と、Updaterの実更新はWindowsで確認してください。
このツール自体は実行物をビルドせず、既存のビルド成果物をパッケージ化します。
