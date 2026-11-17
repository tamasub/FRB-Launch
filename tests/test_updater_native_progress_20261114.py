"""No Tcl/Tk startup dependency, and the interrupted Journal is preserved."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import frb_updater_main
from frb_update import progress_ui
from verify_updater_binary import validate_toc
import pytest


def test_native_ui_has_no_tcl_dependency_in_source_or_build():
    src = (ROOT / 'src/frb_update/progress_ui.py').read_text('utf-8')
    assert 'import tkinter' not in src
    assert 'from tkinter import' not in src
    assert "ctypes.WinDLL('user32'" in src
    bat = (ROOT / '_build_updater_windows.bat').read_text('utf-8')
    assert '--exclude-module tkinter --exclude-module _tkinter' in bat
    assert 'scripts\\verify_updater_binary.py dist\\updater\\FRBUpdater.exe' in bat
    spec = (ROOT / 'FRBUpdater.spec').read_text('utf-8')
    assert "excludes=['tkinter', '_tkinter']" in spec


def test_updater_archive_toc_rejects_tk_runtime():
    validate_toc(['frb_updater_main', 'pyi_rth_inspect', 'PYZ-00.pyz'])
    for bad in ('pyi_rth__tkinter', '_tkinter.pyd', 'tkinter.ttk'):
        with pytest.raises(ValueError, match='Tkinter runtime'):
            validate_toc(['frb_updater_main', bad])


def _pending_journal(tmp_path):
    root = tmp_path / 'FRBLaunch'
    root.mkdir()
    (root / 'FRBLaunch.exe').write_bytes(b'partial-update')
    backup = tmp_path / '.FRBLaunch_update_backups' / 'interrupted'
    (backup / 'files').mkdir(parents=True)
    (backup / 'files' / 'FRBLaunch.exe').write_bytes(b'old-version')
    (backup / 'journal.json').write_text(json.dumps({
        'phase': 'applying', 'touched': ['FRBLaunch.exe']}), 'utf-8')
    return root, backup


def test_updater_ui_init_failure_falls_back_once_to_recover(tmp_path, monkeypatch):
    root, backup = _pending_journal(tmp_path)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local'))
    monkeypatch.setattr(frb_updater_main, 'wait_for_pid', lambda *a, **kw: None)
    monkeypatch.setattr(frb_updater_main, 'ensure_programs_closed', lambda *a, **kw: None)
    monkeypatch.setattr(progress_ui, 'show_progress_window', lambda task, **kw: (_ for _ in ()).throw(
        RuntimeError('Simulated native UI init failure')))
    monkeypatch.setattr(frb_updater_main.sys, 'platform', 'posix')
    monkeypatch.setattr(frb_updater_main.subprocess, 'Popen', lambda *a, **kw: pytest.fail('recover must not restart'))
    rc = frb_updater_main.main(['recover', '--install-root', str(root), '--show-progress'])
    assert rc == 0
    assert (root / 'FRBLaunch.exe').read_bytes() == b'old-version'
    assert json.loads((backup / 'journal.json').read_text('utf-8'))['phase'] == 'rolled_back'
    logs = tmp_path / 'Local/FRBLaunch/UpdateLogs'
    assert json.loads((logs / 'last_update_status.json').read_text('utf-8'))['success']


def test_ui_exception_after_start_does_not_run_recovery_twice(tmp_path, monkeypatch):
    root, backup = _pending_journal(tmp_path)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local'))
    monkeypatch.setattr(frb_updater_main, 'wait_for_pid', lambda *a, **kw: None)
    monkeypatch.setattr(frb_updater_main, 'ensure_programs_closed', lambda *a, **kw: None)
    monkeypatch.setattr(frb_updater_main.sys, 'platform', 'posix')
    calls = []
    def crash_after_start(task, **kw):
        calls.append(task(lambda *a: None))
        raise RuntimeError('GUI terminated after operation')
    monkeypatch.setattr(progress_ui, 'show_progress_window', crash_after_start)
    rc = frb_updater_main.main(['recover', '--install-root', str(root), '--show-progress'])
    assert rc == 1  # UI error is still reported, no second run of the updater.
    assert calls == [0]
    assert (root / 'FRBLaunch.exe').read_bytes() == b'old-version'
    assert json.loads((backup / 'journal.json').read_text('utf-8'))['phase'] == 'rolled_back'


def test_non_windows_progress_callback_calls_task_exactly_once(monkeypatch):
    monkeypatch.setattr(progress_ui.os, 'name', 'posix')
    calls = []
    def task(report):
        calls.append(True)
        report('verify', '100件の確認', 50, 100)
        return 0
    assert progress_ui.show_progress_window(task) == 0
    assert calls == [True]
