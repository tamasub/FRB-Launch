"""Regression for updater recovery encountering WinError 32 on Windows."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from frb_update import updater_core
from frb_update.contracts import UpdateError
import frb_updater_main


def setup_pending(tmp_path):
    root = tmp_path / 'FRBLaunch'
    root.mkdir()
    exe = root / 'FRBLaunch.exe'
    exe.write_bytes(b'partially-written')
    folder = tmp_path / '.FRBLaunch_update_backups' / '20261114_old'
    (folder / 'files').mkdir(parents=True)
    (folder / 'files' / 'FRBLaunch.exe').write_bytes(b'original-exe')
    (folder / 'journal.json').write_text(json.dumps({'phase': 'applying', 'touched': ['FRBLaunch.exe']}), 'utf-8')
    return root, folder, exe


def locked(path):
    exc = PermissionError(13, 'sharing violation', str(path))
    exc.winerror = 32
    return exc


def test_one_transient_lock_is_retried_and_journal_completed(tmp_path, monkeypatch):
    root, folder, exe = setup_pending(tmp_path)
    original_replace = updater_core.os.replace
    attempts = []
    def intermittent(src, dst, *a, **kw):
        if Path(dst) == exe:
            attempts.append(1)
            if len(attempts) == 1:
                raise locked(exe)
        return original_replace(src, dst, *a, **kw)
    monkeypatch.setattr(updater_core.os, 'replace', intermittent)
    monkeypatch.setattr(updater_core.time, 'sleep', lambda *_: None)
    assert updater_core.pending_recovery(root)
    updater_core.recover_interrupted(root)
    assert exe.read_bytes() == b'original-exe'
    assert json.loads((folder / 'journal.json').read_text())['phase'] == 'rolled_back'
    assert not updater_core.pending_recovery(root)
    assert len(attempts) == 2


def test_persistent_lock_keeps_journal_for_later_recovery(tmp_path, monkeypatch):
    root, folder, exe = setup_pending(tmp_path)
    original_replace = updater_core.os.replace
    def blocked(src, dst, *a, **kw):
        if Path(dst) == exe:
            raise locked(exe)
        return original_replace(src, dst, *a, **kw)
    monkeypatch.setattr(updater_core.os, 'replace', blocked)
    monkeypatch.setattr(updater_core.time, 'sleep', lambda *_: None)
    with pytest.raises(UpdateError, match='FRBLaunch.exe'):
        updater_core.recover_interrupted(root)
    assert json.loads((folder / 'journal.json').read_text())['phase'] == 'applying'
    assert updater_core.pending_recovery(root)
    monkeypatch.setattr(updater_core.os, 'replace', original_replace)
    updater_core.recover_interrupted(root)
    assert exe.read_bytes() == b'original-exe'
    assert not updater_core.pending_recovery(root)


def test_updater_does_not_restart_launch_when_rollback_pending(tmp_path, monkeypatch):
    root, folder, exe = setup_pending(tmp_path)
    work = tmp_path / 'LocalAppData'
    monkeypatch.setenv('LOCALAPPDATA', str(work))
    request = tmp_path / 'request.json'
    request.write_text('{}', 'utf-8')
    spawned = []
    monkeypatch.setattr(frb_updater_main, 'wait_for_pid', lambda *a, **kw: None)
    monkeypatch.setattr(frb_updater_main, 'ensure_programs_closed', lambda *a, **kw: None)
    monkeypatch.setattr(frb_updater_main, 'apply_request', lambda *a, **kw: (_ for _ in ()).throw(locked(exe)))
    monkeypatch.setattr(frb_updater_main.subprocess, 'Popen', lambda *a, **kw: spawned.append(a))
    rc = frb_updater_main.main(['apply', '--request', str(request), '--install-root', str(root)])
    assert rc == 1
    assert not spawned, 'Do not restart the host with a half-applied release'
    status = json.loads((work / 'FRBLaunch' / 'UpdateLogs' / 'last_update_status.json').read_text('utf-8'))
    assert not status['success']
    assert '復旧未完了' in status['message']


def test_updater_restarts_old_launch_if_rollback_not_pending(tmp_path, monkeypatch):
    root = tmp_path / 'FRBLaunch'
    root.mkdir()
    (root / 'FRBLaunch.exe').write_bytes(b'old')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'LocalAppData'))
    request = tmp_path / 'request.json'
    request.write_text('{}', 'utf-8')
    spawned = []
    monkeypatch.setattr(frb_updater_main, 'wait_for_pid', lambda *a, **kw: None)
    monkeypatch.setattr(frb_updater_main, 'ensure_programs_closed', lambda *a, **kw: None)
    monkeypatch.setattr(frb_updater_main, 'apply_request', lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('fail')))
    monkeypatch.setattr(frb_updater_main.subprocess, 'Popen', lambda *a, **kw: spawned.append(a))
    rc = frb_updater_main.main(['apply', '--request', str(request), '--install-root', str(root)])
    assert rc == 1
    assert len(spawned) == 1
