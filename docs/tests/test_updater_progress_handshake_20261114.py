"""No invisible update: a visible UI must be acknowledged before file writes."""
import json
import sys
import threading
import time
from pathlib import Path

import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from frb_update.progress_gate import publish_state, activate, activation_path, wait_for_activation
from frb_update import progress_ui
import frb_updater_main
from frb_update.bootstrap import start_updater


def _pending(root):
    root.mkdir()
    (root / 'FRBLaunch.exe').write_bytes(b'partial')
    backup = root.parent / ('.' + root.name + '_update_backups') / 'interrupted'
    (backup / 'files').mkdir(parents=True)
    (backup / 'files' / 'FRBLaunch.exe').write_bytes(b'original')
    (backup / 'journal.json').write_text(json.dumps({'phase': 'applying', 'touched': ['FRBLaunch.exe']}), 'utf-8')
    return backup


def test_launch_must_authorize_updater_before_recovery_changes(tmp_path, monkeypatch):
    root=tmp_path/'FRBLaunch'
    backup=_pending(root)
    ready=tmp_path/'ready_abc.json'
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'Local'))
    monkeypatch.setattr(frb_updater_main,'wait_for_pid',lambda *a,**kw:None)
    monkeypatch.setattr(frb_updater_main,'ensure_programs_closed',lambda *a,**kw:None)
    monkeypatch.setattr(progress_ui.os,'name','posix')
    result=[]
    args=['recover','--install-root',str(root),'--show-progress','--ready-file',str(ready)]
    t=threading.Thread(target=lambda:result.append(frb_updater_main.main(args)),daemon=True)
    t.start()
    for _ in range(80):
        if ready.exists():break
        time.sleep(.05)
    assert ready.exists(), 'Updater did not publish UI startup completion'
    assert json.loads(ready.read_text('utf-8'))['status']=='ready'
    assert (root/'FRBLaunch.exe').read_bytes()==b'partial'
    assert json.loads((backup/'journal.json').read_text('utf-8'))['phase']=='applying'
    activate(ready)
    t.join(timeout=8)
    assert not t.is_alive()
    assert result==[0]
    assert (root/'FRBLaunch.exe').read_bytes()==b'original'
    assert json.loads((backup/'journal.json').read_text('utf-8'))['phase']=='rolled_back'
    assert not activation_path(ready).exists()


def test_apply_fails_closed_if_native_ui_cannot_start(tmp_path,monkeypatch):
    root=tmp_path/'FRBLaunch'
    root.mkdir()
    (root/'FRBLaunch.exe').write_bytes(b'original')
    ready=tmp_path/'ready_123.json'
    monkeypatch.setattr(progress_ui,'show_progress_window',lambda task, **kwargs: (_ for _ in ()).throw(
        OSError('progress window unavailable')))
    monkeypatch.setattr(frb_updater_main,'apply_request',lambda *a, **kw: pytest.fail('headless update forbidden'))
    rc=frb_updater_main.main(['apply','--request',str(tmp_path/'request.json'),
                             '--install-root',str(root), '--show-progress', '--ready-file',str(ready)])
    assert rc==1
    assert (root/'FRBLaunch.exe').read_bytes()==b'original'
    msg=json.loads(ready.read_text('utf-8'))
    assert msg['status']=='error' and 'progress window unavailable' in msg['message']


def test_gate_timeout_does_not_activate(monkeypatch,tmp_path):
    # Intercept time to avoid a 45-second timeout; no marker is created.
    from frb_update import progress_gate
    times=iter([0.0, 1.0])
    monkeypatch.setattr(progress_gate.time,'monotonic',lambda: next(times))
    with pytest.raises(TimeoutError, match='許可'):
        wait_for_activation(tmp_path/'not_approved', timeout=.1)


def test_start_updater_passes_unique_ready_file(monkeypatch,tmp_path):
    import subprocess
    calls=[]
    class FakeProcess: pid=45
    monkeypatch.setattr(subprocess,'Popen',lambda cmd,**kwargs: (calls.append((cmd,kwargs)) or FakeProcess()))
    ready=tmp_path/'ready_unique.json'
    start_updater(tmp_path/'FRBUpdater.exe',request=tmp_path/'request.json',
                  install_root=tmp_path,host_pid=42,ready_file=ready)
    cmd,kw=calls[0]
    assert '--show-progress' in cmd
    assert cmd[cmd.index('--ready-file')+1]==str(ready.resolve())


def test_source_wires_two_way_handshake_and_native_visibility():
    ui=(ROOT/'src/update_information_dialog.py').read_text('utf-8')
    native=(ROOT/'src/frb_update/progress_ui.py').read_text('utf-8')
    assert 'self._ready_timer.start()' in ui
    assert "if info.get('status') != 'ready':" in ui
    assert 'activate(ready)' in ui
    assert 'self._waiting_for_ui' in ui
    assert 'SetWindowPos' in native and 'HWND_TOPMOST' in native
    assert 'PBM_SETMARQUEE' in native
    assert 'on_ready()' in native


def test_native_progress_ui_smoke_without_install_root(tmp_path,monkeypatch):
    # No actual updating should be attempted by the self-test command.
    monkeypatch.setattr(frb_updater_main, 'apply_request',
                        lambda *a,**kw: pytest.fail('ui-test must not apply'))
    monkeypatch.setattr(frb_updater_main, 'recover_interrupted',
                        lambda *a,**kw: pytest.fail('ui-test must not recover'))
    monkeypatch.setattr(frb_updater_main.time, 'sleep', lambda s: None)
    events=[]
    rc=frb_updater_main.main(['ui-test'],progress=lambda *a:events.append(a))
    assert rc==0
    assert any(e[0]=='download' and e[2]==50 for e in events)
    assert any(e[0]=='verify' and e[2]==100 for e in events)
    assert events[-1][0]=='completed'
    assert not list(tmp_path.rglob('journal.json'))
