"""Regression: keyboard focus, graceful third-party close and explicit Obsidian vault URI.

Real cross-process keyboard focus / dirty-document confirmation must be checked
on Windows; these checks verify the state machine and command contracts.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import external_preview_route as route
import studio_win32_host as win32

SRC = Path(__file__).resolve().parents[1] / 'src'


def method(name, module='studio_preview_panel.py', owner='StudioPreviewPanel'):
    tree = ast.parse((SRC / module).read_text(encoding='utf-8'))
    parent = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == owner)
    selected = next(node for node in parent.body if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {}
    exec(compile(ast.Module(body=[selected], type_ignores=[]), name, 'exec'), scope)
    return scope[name]


class Timer:
    def __init__(self):
        self.stopped = False
    def stop(self):
        self.stopped = True


def test_external_embedded_active_sakura_and_obsidian_and_not_studio():
    check = method('external_embedded_active')
    panel = SimpleNamespace(isVisible=lambda: True, _attached=SimpleNamespace(attached=True),
                            _external_key=('sakura', 'file'))
    assert check(panel)
    panel._external_key = ('obsidian', 'file')
    assert check(panel)
    panel._external_key = None
    assert not check(panel)
    panel._external_key = ('sakura', 'file')
    panel._attached.attached = False
    assert not check(panel)


def test_external_focus_is_not_overridden_by_list_and_guards_stay_active():
    source = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    node = ast.parse(source)
    cls = next(n for n in node.body if isinstance(n, ast.ClassDef) and n.name == 'ExpandedLauncherView')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'show_external_preview')
    segment = ast.get_source_segment(source, func)
    assert 'middle.tree.setFocus' not in segment
    assert 'show_external_preview' in segment
    main = (SRC / 'app.py').read_text(encoding='utf-8')
    assert main.count("'external_embedded_active'") == 2
    assert 'external_embedding_pending' in main


def test_stale_sakura_windows_never_receive_implicit_wm_close(monkeypatch):
    actions = []
    monkeypatch.setattr(win32, 'restore_parked_studio_window',
                        lambda hwnd: actions.append(('restore', hwnd)))
    monkeypatch.setattr(win32, 'request_editor_window_close',
                        lambda hwnd: actions.append(('wm_close', hwnd)))
    attached = SimpleNamespace(hwnd=100, detach=lambda **k: actions.append(('detach', k)))
    panel = SimpleNamespace(_external_key=('sakura', 'a'), _attached=attached,
                            _external_pending=None, _sakura_switch_from='old',
                            _external_parked={('sakura', 'b'): 200}, _external_timer=Timer())
    panel._close_owned_sakura = lambda hwnd: actions.append(('ownership_check', hwnd))
    assert method('close_external_editors')(panel) is True
    assert ('detach', {'foreground': False, 'show_window': True}) in actions
    assert ('restore', 200) in actions
    assert not any(x[0] == 'ownership_check' for x in actions)
    assert not any(x[0] == 'wm_close' for x in actions)
    assert panel._external_key is None
    assert panel._external_parked == {}


def test_close_while_pending_refuses_to_hide_unmanaged_editor():
    panel = SimpleNamespace(_external_key=('sakura', 'a'),
                            _attached=None, _external_pending=('pending',),
                            _sakura_switch_from=None, _external_parked={},
                            _external_timer=Timer(), status_label=SimpleNamespace(
                                setText=lambda *args: None, show=lambda: None))
    assert method('close_external_editors')(panel) is False
    assert panel._external_pending == ('pending',)
    assert not panel._external_timer.stopped


def test_close_failure_does_not_kill_or_forget_editor(monkeypatch):
    def refuse(**kwargs):
        raise OSError('detach failed')
    panel = SimpleNamespace(_external_key=('sakura', 'a'), _attached=SimpleNamespace(hwnd=100, detach=refuse),
                            _external_pending=None, _sakura_switch_from=None,
                            _external_parked={}, _external_timer=Timer())
    assert method('close_external_editors')(panel) is False
    assert panel._external_key == ('sakura', 'a')
    assert panel._attached.hwnd == 100


def test_close_callback_calls_external_cleanup_before_hide():
    source = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ExpandedLauncherView')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'close_studio_preview')
    segment = ast.get_source_segment(source, func)
    assert 'close_external_editors' in segment
    assert segment.index('close_external_editors') < segment.index('self._hide_studio_preview_only()')
    native = (SRC / 'studio_win32_host.py').read_text(encoding='utf-8')
    assert 'PostMessageW' in native and '0x0010' in native
    assert 'kernel32.TerminateProcess(' not in native
    assert '.terminate()' not in native


def test_obsidian_prefers_vault_id_for_a_registered_document(tmp_path, monkeypatch):
    appdata = tmp_path / 'appdata'
    vault = tmp_path / 'vault Japanese 日本語'
    note = vault / 'my files' / 'テスト.md'
    note.parent.mkdir(parents=True)
    note.write_text('# test', encoding='utf-8')
    registry = appdata / 'obsidian' / 'obsidian.json'
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({'vaults': {'approved-vault-id': {'path': str(vault), 'ts': 1}}}),
                        encoding='utf-8')
    monkeypatch.setenv('APPDATA', str(appdata))
    uri = route.obsidian_open_uri(str(note))
    assert uri.startswith('obsidian://open?vault=approved-vault-id&file=my%20files%2F')
    assert 'paneType=' not in uri
    assert 'path=' not in uri
    assert '%E3%83%86' in uri


def test_obsidian_strict_uri_does_not_send_unknown_vault(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setenv('APPDATA', str(tmp_path / 'empty_appdata'))
    with pytest.raises(ValueError, match='Vault'):
        route.obsidian_open_uri(str(tmp_path / 'missing.md'), require_registered=True)
