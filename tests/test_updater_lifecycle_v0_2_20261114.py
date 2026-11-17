"""Lifecycle and progress regression for independent Updater."""
import hashlib
import json
import sys
import threading
import zipfile
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from frb_update import updater_core
from frb_update.contracts import UpdateError
from frb_update.bootstrap import start_updater


def pkg(path, version, launch, studio=b'studio'):
    files={'FRBLaunch.exe':launch,'Studio/NativeShell/_publish/FRBStudio.NativeShell.exe':studio}
    manifest={'schema':'frb-system-package-v1','product':'FRBLaunchIntegrated','version':version,
              'components':{'launch':'0.9.0','studio':'0.9.0'},
              'files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('release.json',json.dumps(manifest))
        for name,value in files.items():z.writestr('system/'+name,value)
    return manifest


def test_recovery_skips_unchanged_binary_in_legacy_journal(tmp_path,monkeypatch):
    root=tmp_path/'FRBLaunch';root.mkdir()
    exe=root/'FRBLaunch.exe';exe.write_bytes(b'old')
    backups=tmp_path/'.FRBLaunch_update_backups'/'old_legacy';(backups/'files').mkdir(parents=True)
    (backups/'files'/'FRBLaunch.exe').write_bytes(b'old')
    (backups/'journal.json').write_text(json.dumps({'phase':'applying','touched':['FRBLaunch.exe']}),'utf-8')
    original_replace=updater_core.os.replace
    def locked(*args,**kwargs):
        if Path(args[1])==exe:raise AssertionError('unchanged EXE should never be replaced')
        return original_replace(*args,**kwargs)
    monkeypatch.setattr(updater_core.os,'replace',locked)
    updater_core.recover_interrupted(root)
    assert exe.read_bytes()==b'old'
    assert json.loads((backups/'journal.json').read_text())['phase']=='rolled_back'


def test_same_content_new_version_does_not_replace_binary(tmp_path,monkeypatch):
    root=tmp_path/'FRBLaunch';root.mkdir()
    exe=root/'FRBLaunch.exe';exe.write_bytes(b'unchanged')
    one=tmp_path/'one.zip';two=tmp_path/'two.zip'
    pkg(one,'0.9.0',b'unchanged')
    pkg(two,'0.9.1',b'unchanged')
    updater_core.install_zip(one,root)
    original_replace=updater_core.os.replace
    def guard(src,dst,*args,**kwargs):
        if Path(dst)==exe:raise AssertionError('already identical EXE should not be replaced')
        return original_replace(src,dst,*args,**kwargs)
    monkeypatch.setattr(updater_core.os,'replace',guard)
    progress=[]
    updater_core.install_zip(two,root,progress=lambda *e:progress.append(e))
    assert json.loads((root/'installed_release.json').read_text())['version']=='0.9.1'
    assert any(e[0]=='completed' for e in progress)


def test_pending_journal_restored_before_update(tmp_path):
    root=tmp_path/'FRBLaunch';root.mkdir()
    exe=root/'FRBLaunch.exe';exe.write_bytes(b'partial')
    backups=tmp_path/'.FRBLaunch_update_backups'/'pending'
    (backups/'files').mkdir(parents=True)
    (backups/'files'/'FRBLaunch.exe').write_bytes(b'old')
    (backups/'journal.json').write_text(json.dumps({'phase':'applying','touched':['FRBLaunch.exe']}),'utf-8')
    archive=tmp_path/'new.zip';pkg(archive,'0.9.1',b'new')
    updater_core.install_zip(archive,root)
    assert exe.read_bytes()==b'new'
    assert json.loads((backups/'journal.json').read_text())['phase']=='rolled_back'


def test_update_lock_rejects_concurrent_process(tmp_path):
    root=tmp_path/'FRBLaunch';root.mkdir()
    with updater_core.update_lock(root):
        with pytest.raises(UpdateError, match='別のUpdater'):
            with updater_core.update_lock(root):pass
    with updater_core.update_lock(root):pass


def test_bootstrap_launches_visible_updater(tmp_path,monkeypatch):
    import subprocess
    args=[]
    class FakeProcess:
        pid=1234
    monkeypatch.setattr(subprocess,'Popen',lambda cmd,**kw: (args.append(cmd) or FakeProcess()))
    start_updater(tmp_path/'updater.exe',request=tmp_path/'request.json',install_root=tmp_path,
                  host_pid=111,allow_local=True)
    assert '--show-progress' in args[0]


def test_winerror5_on_executable_retries_once(monkeypatch,tmp_path):
    dest=tmp_path/'FRBLaunch.exe'
    attempts=[]
    def action():
        attempts.append(1)
        if len(attempts)==1:
            exc=PermissionError(13,'access denied',str(dest))
            exc.winerror=5
            raise exc
        return 'ok'
    monkeypatch.setattr(updater_core.time,'sleep',lambda n:None)
    assert updater_core._retry_locked_file(action,dest)=='ok'
    assert len(attempts)==2


def test_recover_command_does_not_restart_launch(tmp_path,monkeypatch):
    import frb_updater_main
    root=tmp_path/'FRBLaunch';root.mkdir()
    (root/'FRBLaunch.exe').write_bytes(b'partial')
    backup=tmp_path/'.FRBLaunch_update_backups'/'old'
    (backup/'files').mkdir(parents=True)
    (backup/'files'/'FRBLaunch.exe').write_bytes(b'old')
    (backup/'journal.json').write_text(json.dumps({'phase':'applying','touched':['FRBLaunch.exe']}),'utf-8')
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'LocalData'))
    monkeypatch.setattr(frb_updater_main,'wait_for_pid',lambda *a,**kw:None)
    monkeypatch.setattr(frb_updater_main,'ensure_programs_closed',lambda *a,**kw:None)
    monkeypatch.setattr(frb_updater_main.subprocess,'Popen',lambda *a,**kw:pytest.fail('recover must not restart'))
    result=frb_updater_main.main(['recover','--install-root',str(root)])
    assert result==0
    assert (root/'FRBLaunch.exe').read_bytes()==b'old'
    assert json.loads((backup/'journal.json').read_text())['phase']=='rolled_back'


def test_restart_failure_is_not_reported_success(tmp_path,monkeypatch):
    import frb_updater_main
    root=tmp_path/'FRBLaunch';root.mkdir()
    (root/'FRBLaunch.exe').write_bytes(b'valid')
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'LocalData'))
    monkeypatch.setattr(frb_updater_main,'wait_for_pid',lambda *a,**kw:None)
    monkeypatch.setattr(frb_updater_main,'ensure_programs_closed',lambda *a,**kw:None)
    monkeypatch.setattr(frb_updater_main,'apply_request',lambda *a,**kw: tmp_path/'backup')
    def fail(*a,**kw):raise OSError('restart unavailable')
    monkeypatch.setattr(frb_updater_main.subprocess,'Popen',fail)
    request=tmp_path/'request.json';request.write_text('{}','utf-8')
    assert frb_updater_main.main(['apply','--request',str(request),'--install-root',str(root)])==1
    status=json.loads((tmp_path/'LocalData'/'FRBLaunch'/'UpdateLogs'/'last_update_status.json').read_text())
    assert status['success'] is False
    assert 'restart unavailable' in status['message']
