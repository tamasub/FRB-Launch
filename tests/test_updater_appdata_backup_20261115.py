"""New LocalAppData backups and legacy recovery must coexist safely."""
import json
from pathlib import Path

from frb_update import updater_core as core


def test_new_root_is_per_install_and_inside_local_appdata(tmp_path, monkeypatch):
    local = tmp_path / 'localappdata'
    monkeypatch.setenv('LOCALAPPDATA', str(local))
    a = tmp_path / 'a' / 'FRBLaunch'
    b = tmp_path / 'b' / 'FRBLaunch'
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    x, y = core.backup_root(a), core.backup_root(b)
    assert x != y
    assert x.parent == local / 'FRBLaunch' / 'UpdateBackups'
    assert y.parent == x.parent
    assert core.legacy_backup_root(a) in core.backup_roots_for_recovery(a)


def test_old_and_new_pending_journals_detected(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'appdata'))
    root = tmp_path / 'test' / 'FRBLaunch'
    root.mkdir(parents=True)
    old = core.legacy_backup_root(root) / 'old'
    old.mkdir(parents=True)
    (old / 'journal.json').write_text(json.dumps({'phase': 'applying', 'touched': []}), 'utf-8')
    assert core.pending_recovery(root)
    core.recover_interrupted(root)
    assert json.loads((old / 'journal.json').read_text('utf-8'))['phase'] == 'rolled_back'
    new = core.backup_root(root) / 'new'
    new.mkdir(parents=True)
    (new / 'journal.json').write_text(json.dumps({'phase': 'applying', 'touched': []}), 'utf-8')
    assert core.pending_recovery(root)
    core.recover_interrupted(root)
    assert json.loads((new / 'journal.json').read_text('utf-8'))['phase'] == 'rolled_back'
    assert not core.pending_recovery(root)


def test_old_completed_journal_left_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'appdata'))
    root = tmp_path / 'FRBLaunch'
    root.mkdir()
    old = core.legacy_backup_root(root) / 'completed'
    old.mkdir(parents=True)
    file = old / 'journal.json'
    content = json.dumps({'phase': 'completed', 'touched': ['FRBLaunch.exe']})
    file.write_text(content, 'utf-8')
    core.recover_interrupted(root)
    assert file.read_text('utf-8') == content


def test_install_zip_writes_new_backup_only_to_appdata(tmp_path, monkeypatch):
    import hashlib
    import zipfile
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'localappdata'))
    root = tmp_path / 'Install' / 'FRBLaunch'
    root.mkdir(parents=True)
    (root / 'FRBLaunch.exe').write_bytes(b'oldexe')
    files = {
        'FRBLaunch.exe': b'newexe',
        'Studio/NativeShell/_publish/FRBStudio.NativeShell.exe': b'studio',
    }
    manifest = {
        'schema': 'frb-system-package-v1', 'product': 'FRBLaunchIntegrated',
        'version': '0.9.6', 'components': {'launch': '0.9.3', 'studio': '0.9.0'},
        'files': {key: hashlib.sha256(value).hexdigest() for key, value in files.items()},
    }
    archive = tmp_path / 'release.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('release.json', json.dumps(manifest))
        for name, data in files.items():
            z.writestr('system/' + name, data)
    backup = core.install_zip(archive, root)
    assert backup.parent == core.backup_root(root)
    assert (backup / 'journal.json').is_file()
    assert json.loads((backup / 'journal.json').read_text('utf-8'))['phase'] == 'completed'
    assert (backup / 'files' / 'FRBLaunch.exe').read_bytes() == b'oldexe'
    assert not core.legacy_backup_root(root).exists()
