"""Internal Studio CLI never creates a console; protocol and explicit Run stay intact."""
import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import launch_menu_registration as registration
import process_runner


@pytest.fixture
def windows_console(monkeypatch):
    # Do not change global os.name: pathlib must remain native to the test host.
    monkeypatch.setattr(process_runner, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000, raising=False)
    monkeypatch.setattr(subprocess, 'CREATE_NEW_CONSOLE', 0x10, raising=False)


def test_windows_internal_cli_retains_request_response_and_timeout(windows_console):
    response = subprocess.CompletedProcess(['node'], 0, '応答', '')
    with patch.object(subprocess, 'run', return_value=response) as run:
        assert process_runner.run_internal_process(
            ['node', 'cli.mjs'], input='日本語', text=True, encoding='utf-8',
            capture_output=True, timeout=40, check=False) is response
    run.assert_called_once_with(['node', 'cli.mjs'], input='日本語', text=True,
                                encoding='utf-8', capture_output=True, timeout=40,
                                check=False, creationflags=0x08000000)


@pytest.mark.parametrize('show_console,flags', [(True, 0x10), (False, 0x08000000)])
def test_explicit_console_launch_policy_unchanged(windows_console, show_console, flags):
    with patch.object(subprocess, 'Popen') as spawn:
        process_runner.start_process('cmd.exe', ['/c', 'example.bat'], '.', show_console)
    kwargs = spawn.call_args.kwargs
    assert kwargs['creationflags'] == flags
    if show_console:
        assert not {'stdin', 'stdout', 'stderr'} & kwargs.keys()
    else:
        assert all(kwargs[k] == subprocess.DEVNULL for k in ('stdin', 'stdout', 'stderr'))


def test_non_windows_internal_cli_roundtrip(monkeypatch):
    monkeypatch.setattr(process_runner, 'os', SimpleNamespace(name='posix'))
    if sys.platform == 'win32':
        pytest.skip('real non-Windows process roundtrip')
    result = process_runner.run_internal_process(
        [sys.executable, '-c', 'import sys; print(sys.stdin.read()); print("diagnostic", file=sys.stderr)'],
        input='日本語', text=True, encoding='utf-8', capture_output=True, timeout=10)
    assert result.returncode == 0
    assert result.stdout.strip() == '日本語'
    assert result.stderr.strip() == 'diagnostic'


@pytest.fixture
def config(tmp_path):
    p = tmp_path / 'config' / 'launch.json'
    p.parent.mkdir()
    p.write_text(json.dumps({'pages': [{'page_id': 'work', 'enabled': True}], 'items': [
        {'page_id': 'work', 'item_id': 'existing', 'parent_item_id': '', 'item_kind': 'command', 'title': '既存'}]}), encoding='utf-8')
    return p


@pytest.mark.parametrize('kind', ['file', 'directory'])
def test_drop_add_preview_and_commit_both_hidden(windows_console, monkeypatch, config, tmp_path, kind):
    monkeypatch.setattr(registration, '_node_binary', lambda *a: 'node.exe')
    source = tmp_path / '登録対象'
    if kind == 'directory':
        source.mkdir()
    else:
        source.write_text('data', encoding='utf-8')
    records = registration.records_for_sources(registration.normalize_sources([{'value': str(source)}]))
    calls = []
    def fake_cli(command, **kwargs):
        request = json.loads(kwargs['input'])
        calls.append((request, kwargs))
        assert command[0] == 'node.exe'
        assert command[1].endswith('tools/change_core/cli.mjs') or command[1].replace('\\', '/').endswith('tools/change_core/cli.mjs')
        assert kwargs['creationflags'] == 0x08000000
        assert kwargs['capture_output'] and kwargs['encoding'] == 'utf-8'
        assert kwargs['timeout'] == 40 and kwargs['check'] is False
        return subprocess.CompletedProcess(command, 0, json.dumps({
            'status': 'PREVIEW' if request['mode'] == 'dry_run' else 'COMMITTED',
            'summary': {'added': len(records)}}), '')
    monkeypatch.setattr(subprocess, 'run', fake_cli)
    before = config.read_bytes()
    result = registration.commit_add(config, tmp_path, 'work', '', records)
    assert result['status'] == 'COMMITTED'
    assert [req['mode'] for req, _ in calls] == ['dry_run', 'commit']
    assert calls[0][0]['operations'] == calls[1][0]['operations']
    assert calls[0][0]['base_sha256'] == calls[1][0]['base_sha256']
    assert config.read_bytes() == before  # Python does not write authoritative JSON.


def test_shared_change_core_delete_preview_and_commit_both_hidden(windows_console, monkeypatch, config, tmp_path):
    monkeypatch.setattr(registration, '_node_binary', lambda *a: 'node.exe')
    modes = []
    def fake_cli(command, **kwargs):
        request = json.loads(kwargs['input'])
        mode = request['mode']
        modes.append(mode)
        assert kwargs['creationflags'] == 0x08000000
        assert kwargs['capture_output'] and kwargs['encoding'] == 'utf-8'
        return subprocess.CompletedProcess(command, 0, json.dumps({
            'status': 'PREVIEW' if mode == 'dry_run' else 'COMMITTED',
            'base_sha256': request['base_sha256'], 'saved': mode == 'commit',
            'summary': {'deleted': 1}, 'expected_diff': [], 'actual_diff': []}), '')
    monkeypatch.setattr(subprocess, 'run', fake_cli)
    plan = registration.prepare_delete(config, tmp_path, 'work', 'existing')
    assert registration.commit_delete(plan)['status'] == 'COMMITTED'
    assert modes == ['dry_run', 'commit']


def test_preview_error_still_stops_commit(windows_console, monkeypatch, config, tmp_path):
    monkeypatch.setattr(registration, '_node_binary', lambda *a: 'node.exe')
    with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired('node', 40)) as run:
        with pytest.raises(registration.RegistrationError):
            registration.commit_add(config, tmp_path, 'work', '', [registration.category_record('追加')])
    assert run.call_count == 1
    assert run.call_args.kwargs['creationflags'] == 0x08000000
