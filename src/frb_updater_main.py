"""FRB Updater executable. Build as a separate --onefile Windows EXE."""
import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from frb_update.updater_core import apply_request, ensure_programs_closed, wait_for_pid
from frb_update.contracts import UpdateError

def main(argv=None):
    parser=argparse.ArgumentParser(description='FRB system-only updater')
    parser.add_argument('command',choices=['apply'])
    parser.add_argument('--request',required=True,type=Path)
    parser.add_argument('--install-root',required=True,type=Path)
    parser.add_argument('--wait-pid',type=int,default=0)
    parser.add_argument('--host-exe',default='FRBLaunch.exe')
    parser.add_argument('--allow-local-for-test',action='store_true')
    args=parser.parse_args(argv)
    root=args.install_root.resolve()
    logdir=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'FRBLaunch' / 'UpdateLogs'
    logdir.mkdir(parents=True,exist_ok=True)
    logpath=logdir/('updater_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.log')
    statuspath=logdir/'last_update_status.json'
    def record_status(success, message, backup=None):
        temp=statuspath.with_suffix('.tmp')
        temp.write_text(json.dumps({'success':success,'message':str(message),
           'backup':str(backup) if backup else None,
           'time':datetime.now().isoformat(timespec='seconds')},ensure_ascii=False,indent=2)+'\n','utf-8')
        os.replace(temp,statuspath)
    def log(msg):
        with logpath.open('a',encoding='utf-8') as fp:fp.write(msg+'\n')
        print(msg,flush=True)
    try:
        log('[START] '+str(root))
        wait_for_pid(args.wait_pid)
        ensure_programs_closed()
        location=apply_request(args.request,root,allow_local=args.allow_local_for_test)
        log('[SUCCESS] rollback files: '+str(location))
        record_status(True,'Launch統合版を更新しました。',location)
        if Path(args.host_exe).name != args.host_exe:
            raise UpdateError('Launchファイル名が不正です')
        binary=root/args.host_exe
        if not binary.is_file(): raise UpdateError('更新後のLaunch.exeが見つかりません')
        subprocess.Popen([str(binary)],cwd=str(root),close_fds=True)
        return 0
    except Exception as exc:
        log('[FAILED] '+str(exc))
        log(traceback.format_exc())
        record_status(False,exc)
        # Return to the previous Launch after rollback, not a blank desktop.
        fallback=root/args.host_exe
        if fallback.is_file():
            try:subprocess.Popen([str(fallback)],cwd=str(root),close_fds=True)
            except Exception as restart_error:log('[RESTART FAILED] '+str(restart_error))
        return 1

if __name__=='__main__':
    raise SystemExit(main())
