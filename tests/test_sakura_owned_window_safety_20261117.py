"""Regression: Launch may close its own Sakura windows, never pre-existing ones.

No Windows GUI is needed for these ownership/lifecycle contract tests.
Full GUI behavior and save prompts must still be verified on Windows.
"""
import ast
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import external_win32_host as external

SOURCE = Path(__file__).resolve().parents[1] / 'src'


def method(name):
    tree = ast.parse((SOURCE / 'studio_preview_panel.py').read_text(encoding='utf-8'))
    klass = next(item for item in tree.body if isinstance(item, ast.ClassDef)
                 and item.name == 'StudioPreviewPanel')
    node = next(item for item in klass.body if isinstance(item, ast.FunctionDef)
                and item.name == name)
    context = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<test>', 'exec'), context)
    return context[name]


class Timer:
    def stop(self):
        pass


def test_existing_sakura_process_is_never_selected_even_when_hwnd_appears_new(monkeypatch):
    from external_preview_route import ExternalPreviewTarget
    target = ExternalPreviewTarget('sakura', r'C:\\notes\\a.txt', 'sakura.exe')
    monkeypatch.setattr(external, 'editor_windows', lambda app: [
        (201, 1100, 'a.txt - サクラエディタ'),
        (301, 1200, 'a.txt - サクラエディタ'),
    ])
    # 201 belongs to a user-owned process that existed before launch.
    assert external.find_new_editor_window(target, {101}, 1200, {1100}) == 301
    # If only the standalone process reuses/creates a window, do not dock it.
    monkeypatch.setattr(external, 'editor_windows', lambda app: [
        (201, 1100, 'a.txt - サクラエディタ')
    ])
    assert external.find_new_editor_window(target, {101}, 1200, {1100}) is None


def test_preexisting_sakura_is_never_sent_wm_close(monkeypatch):
    calls = []
    native = types.ModuleType('external_win32_host')
    native.editor_window_pid = lambda hwnd: 1100
    close = types.ModuleType('studio_win32_host')
    close.request_editor_window_close = lambda hwnd: calls.append(hwnd)
    obj = SimpleNamespace(_sakura_owned_windows={})
    with patch.dict(sys.modules, {'external_win32_host': native, 'studio_win32_host': close}):
        assert method('_close_owned_sakura')(obj, 201) is True
        assert calls == []


def test_only_launch_owned_sakura_hwnd_may_close(monkeypatch):
    calls = []
    native = types.ModuleType('external_win32_host')
    native.editor_window_pid = lambda hwnd: 1200
    close = types.ModuleType('studio_win32_host')
    close.request_editor_window_close = lambda hwnd: calls.append(hwnd)
    obj = SimpleNamespace(_sakura_owned_windows={301: 1200})
    with patch.dict(sys.modules, {'external_win32_host': native, 'studio_win32_host': close}):
        assert method('_close_owned_sakura')(obj, 301) is True
        assert calls == [301]
        assert obj._sakura_owned_windows == {}
        # Repeating × must not send another WM_CLOSE.
        assert method('_close_owned_sakura')(obj, 301) is True
        assert calls == [301]


def test_reused_hwnd_with_another_pid_is_never_closed():
    calls = []
    native = types.ModuleType('external_win32_host')
    native.editor_window_pid = lambda hwnd: 9999
    close = types.ModuleType('studio_win32_host')
    close.request_editor_window_close = lambda hwnd: calls.append(hwnd)
    obj = SimpleNamespace(_sakura_owned_windows={301: 1200})
    with patch.dict(sys.modules, {'external_win32_host': native, 'studio_win32_host': close}):
        assert method('_close_owned_sakura')(obj, 301) is True
    assert calls == []


def test_panel_close_restores_unowned_window_but_does_not_close_it():
    events = []
    native = types.ModuleType('studio_win32_host')
    native.request_editor_window_close = lambda hwnd: events.append(('wm_close', hwnd))
    active = SimpleNamespace(hwnd=201,
                             detach=lambda **kw: events.append(('detach', kw)))
    obj = SimpleNamespace(_external_pending=None, _external_timer=Timer(),
                          _sakura_switch_from=None, _external_key=('sakura', 'file'),
                          _attached=active, _external_parked={},
                          _sakura_owned_windows={})
    obj._close_owned_sakura = lambda hwnd: method('_close_owned_sakura')(obj, hwnd)
    with patch.dict(sys.modules, {'studio_win32_host': native}):
        assert method('close_external_editors')(obj) is True
    assert events == [('detach', {'foreground': False, 'show_window': True})]
    assert obj._external_key is None


def test_switching_away_from_docked_sakura_is_refused():
    events = []
    win = SimpleNamespace(hwnd=201, attached=True,
                          detach=lambda **kw: events.append(('detach', kw)))
    obj = SimpleNamespace(_external_key=('sakura', 'file'), _external_timer=Timer(),
                          _sakura_switch_from=None, _external_pending=None,
                          _attached=win, _external_parked={},
                          _sakura_owned_windows={})
    obj._close_owned_sakura = lambda hwnd: method('_close_owned_sakura')(obj, hwnd)
    assert method('_park_external')(obj) is False
    assert events == []
    assert obj._external_key == ('sakura', 'file')


def test_keyboard_focus_fix_unchanged():
    panel = (SOURCE / 'studio_preview_panel.py').read_text(encoding='utf-8')
    win32 = (SOURCE / 'studio_win32_host.py').read_text(encoding='utf-8')
    assert "self._external_key[0] not in ('obsidian', 'sakura')" in panel
    assert 'focus_embedded_editor_from_click' in win32
    assert 'AttachThreadInput' in win32
