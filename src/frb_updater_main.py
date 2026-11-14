"""FRB Updater executable. Build as a separate --onefile Windows EXE."""
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from frb_update.updater_core import (apply_request, ensure_programs_closed, wait_for_pid,
                                    pending_recovery, recover_interrupted, update_lock)
from frb_update.contracts import UpdateError

def main(argv=None, *, progress=None):
    parser=argparse.ArgumentParser(description='FRB system-only updater')
    parser.add_argument('command',choices=['apply','recover','ui-test'])
    parser.add_argument('--request',type=Path)
    parser.add_argument('--install-root',type=Path)
    parser.add_argument('--wait-pid',type=int,default=0)
    parser.add_argument('--host-exe',default='FRBLaunch.exe')
    parser.add_argument('--allow-local-for-test',action='store_true')
    parser.add_argument('--show-progress',action='store_true')
    parser.add_argument('--ready-file',type=Path,default=None,
                        help='Launch/Updater native UI readiness handshake')
    if '--ready-file' in (argv if argv is not None else sys.argv[1:]) and '--show-progress' not in (argv if argv is not None else sys.argv[1:]):
        parser.error('--ready-file requires --show-progress')
    args=parser.parse_args(argv)
    if args.show_progress and progress is None:
        # Keep --ready-file out of the recursive worker invocation.
        raw = list(argv if argv is not None else sys.argv[1:])
        raw.remove('--show-progress')
        if '--ready-file' in raw:
            index = raw.index('--ready-file')
            del raw[index:index + 2]
        started = {'value': False}
        from frb_update.progress_gate import publish_state, wait_for_activation

        def guarded_run(report):
            started['value'] = True
            # It is unsafe to modify the installation until Launch confirms it
            # has actually observed the Updater's native progress window.
            if args.ready_file is not None:
                report('wait', 'Launchからの更新開始許可を待っています')
                wait_for_activation(args.ready_file)
            return main(raw, progress=report)

        def ui_ready():
            if args.ready_file is not None:
                publish_state(args.ready_file, 'ready')

        try:
            from frb_update.progress_ui import show_progress_window
            return show_progress_window(guarded_run, on_ready=ui_ready)
        except Exception as gui_error:
            # APPLY MUST FAIL CLOSED. Never secretly continue a GUI-triggered
            # update in headless mode, and never run an operation twice.
            if args.ready_file is not None and not started['value']:
                try:
                    publish_state(args.ready_file, 'error', str(gui_error))
                except OSError:
                    pass
            code = (main(raw) if args.command == 'recover' and not started['value']
                    and args.ready_file is None else 1)
            if sys.platform == 'win32' and args.ready_file is None:
                try:
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(
                        None, '進捗画面の起動に失敗しました。更新の自動続行はしません。\n'
                              + str(gui_error), 'FRB Updater', 0x10)
                except Exception:
                    pass
            return code
    if args.command == 'ui-test':
        # Safe native UI smoke: no update lock, Journal, downloads, or files.
        # Useful even after the latest integrated product is installed.
        if progress is not None:
            progress('wait', '進捗ウィンドウ単体テスト（更新は実行しません）')
            time.sleep(.25)
            for phase, label in [('download', 'ダウンロード表示'),
                                 ('verify', '検証表示'),
                                 ('apply', '適用表示')]:
                for i in range(0, 101, 10):
                    progress(phase, f'画面テスト: {label} ({i}%)', i, 100)
                    time.sleep(.10)
            progress('completed', '画面テスト完了。実際の製品ファイルは変更していません。', 100, 100)
        return 0
    if args.install_root is None:
        parser.error('apply / recover には --install-root が必要です')
    if args.command == 'apply' and args.request is None:
        parser.error('apply には --request が必要です')
    root=args.install_root.resolve()
    logdir=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'FRBLaunch' / 'UpdateLogs'
    logdir.mkdir(parents=True,exist_ok=True)
    logpath=logdir/('updater_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.log')
    statuspath=logdir/'last_update_status.json'
    def record_status(success, message, backup=None):
        temp=statuspath.with_suffix('.tmp')
        temp.write_text(json.dumps({'success':success,'message':str(message),
           'backup':str(backup) if backup else None,
           'install_root':str(root),
           'time':datetime.now().isoformat(timespec='seconds')},ensure_ascii=False,indent=2)+'\n','utf-8')
        os.replace(temp,statuspath)
    def log(msg):
        with logpath.open('a',encoding='utf-8') as fp:fp.write(msg+'\n')
        print(msg,flush=True)
    def report(stage, message, current=None, total=None):
        log('[%s] %s' % (stage.upper(), message)) if current is None or current == total else None
        if progress is not None:
            progress(stage, message, current, total)
    applied = False
    acquired = False
    try:
        log('[START] '+str(root))
        with update_lock(root):
            acquired = True
            report('wait','Launch・Studioの終了を確認しています')
            wait_for_pid(args.wait_pid)
            ensure_programs_closed()
            if args.command == 'recover':
                if not pending_recovery(root):
                    record_status(True,'復旧対象の中断Journalはありません。')
                    report('completed','復旧を必要とする中断Journalはありません')
                    return 0
                recover_interrupted(root, progress=report)
                record_status(True,'中断した更新を旧版へ復旧しました。')
                report('completed','旧版への復旧が完了しました')
                return 0
            location=apply_request(args.request,root,allow_local=args.allow_local_for_test, progress=report)
            applied = True
            log('[SUCCESS] rollback files: '+str(location))
            if Path(args.host_exe).name != args.host_exe:
                raise UpdateError('Launchファイル名が不正です')
            binary=root/args.host_exe
            if not binary.is_file(): raise UpdateError('更新後のLaunch.exeが見つかりません')
            report('restart','新しいFRB Launchを起動しています')
            subprocess.Popen([str(binary)],cwd=str(root),close_fds=True)
            record_status(True,'Launch統合版を更新し、Launchを再起動しました。',location)
            report('completed','更新成功。新しいLaunchを起動しました')
            return 0
    except Exception as exc:
        log('[FAILED] '+str(exc))
        log(traceback.format_exc())
        if pending_recovery(root):
            # A restarted Launch could lock the same files and prevent rollback
            # from completing. Keep the journal so the next attempt can recover.
            detail = ('復旧未完了です。Launchを起動しないでください。'
                      'すべてのLaunch／Studioを終了し、Updaterを再実行してください。 '
                      + str(exc))
            log('[RECOVERY PENDING] ' + detail)
            record_status(False, detail)
            report('failed',detail)
            return 1
        record_status(False,exc)
        report('failed',('更新ファイルは適用済みですが、Launchの再起動に失敗: ' if applied else '更新失敗: ') + str(exc))
        # Do not race another Updater, or relaunch an already-updated application.
        if not acquired or applied or args.command == 'recover':
            return 1
        # Restart only after rollback is complete (or no files were modified).
        fallback=root/args.host_exe
        if fallback.is_file():
            try:subprocess.Popen([str(fallback)],cwd=str(root),close_fds=True)
            except Exception as restart_error:log('[RESTART FAILED] '+str(restart_error))
        return 1

if __name__=='__main__':
    raise SystemExit(main())
