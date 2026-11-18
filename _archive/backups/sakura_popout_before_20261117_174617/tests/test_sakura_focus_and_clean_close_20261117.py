"""Sakura HWND focus and lifecycle safety; Win32 GUI input still needs manual testing."""
import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import types
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'src'


def _method(name):
    tree = ast.parse((SOURCE / 'studio_preview_panel.py').read_text(encoding='utf-8'))
    klass = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'StudioPreviewPanel')
    method = next(x for x in klass.body if isinstance(x, ast.FunctionDef) and x.name == name)
    context = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), name, 'exec'), context)
    return context[name]


class Timer:
    def stop(self):
        self.stopped = True


def test_sakura_switch_detaches_without_closing_unowned_window():
    actions = []

    def detach(**kw):
        actions.append(('detach', kw))
        win.attached = False

    win = SimpleNamespace(hwnd=77, attached=True, detach=detach)
    panel = SimpleNamespace(_external_key=('sakura', 'file1'),
                            _attached=win, _external_parked={}, _external_pending=None,
                            _sakura_switch_from=None, _external_timer=Timer(),
                            _sakura_owned_windows={})
    # Existing standalone window is unowned and must not receive WM_CLOSE.
    close = _method('_close_owned_sakura')
    panel._close_owned_sakura = lambda hwnd: close(panel, hwnd)
    _method('_park_external')(panel)
    assert actions == [('detach', {'foreground': False, 'show_window': True})]
    assert panel._external_key is None
    assert panel._attached is None
    assert panel._external_parked == {}


def test_obsidian_still_parks_hidden_and_preserves_session():
    actions = []
    win = SimpleNamespace(hwnd=99, attached=True, detach=lambda **kw: actions.append(kw))
    panel = SimpleNamespace(_external_key=('obsidian', 'note.md'),
                            _attached=win, _external_parked={}, _external_pending=None,
                            _sakura_switch_from=None, _external_timer=Timer())
    _method('_park_external')(panel)
    assert actions == [{'foreground': False, 'show_window': False}]
    assert panel._external_parked == {('obsidian', 'note.md'): 99}


def test_close_failure_never_force_kills_sakura():
    def fail(**kw):
        raise OSError('fail')
    win = SimpleNamespace(hwnd=77, attached=True, detach=fail)
    panel = SimpleNamespace(_external_key=('sakura', 'file1'),
                            _attached=win, _external_parked={}, _external_pending=None,
                            _sakura_switch_from=None, _external_timer=Timer())
    _method('_park_external')(panel)
    assert panel._attached is win
    assert panel._external_key == ('sakura', 'file1')
    assert panel._external_parked == {}


def test_no_process_kill_or_keyboard_injection():
    source = (SOURCE / 'studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'self._close_owned_sakura(attached.hwnd)' in source
    assert '.kill(' not in source and '.terminate(' not in source
    app = (SOURCE / 'app.py').read_text(encoding='utf-8')
    assert 'preview.focus_external_after_native_click(x, y)' in app
    assert 'on_embedded_mouse_release=focus_docked_external_on_mouse_release' in app


def test_sakura_caption_reads_directly_from_embedded_hwnd(monkeypatch):
    """Top-level enumeration cannot find a child HWND after SetParent."""
    import external_win32_host as native
    import ctypes
    from ctypes import wintypes
    class User32:
        def GetWindowTextLengthW(self, hwnd):
            assert hwnd == 707
            return 9
        def GetWindowTextW(self, hwnd, buf, length):
            assert hwnd == 707 and length == 10
            buf.value = 'file2.ini'
            return 9
    monkeypatch.setattr(native, '_api', lambda: (User32(), None))
    assert native.editor_window_title(707) == 'file2.ini'
    assert native.editor_window_title(0) == ''
