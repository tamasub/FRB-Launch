"""Launch-owned NativeShell is hidden until the third-column SetParent ACK.

These tests exercise the real Win32 window-selection algorithm with an
in-memory user32. They do not claim a real Windows GUI test.
"""
import ast
import ctypes
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace as NS

import studio_win32_host as win

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'src' / 'studio_preview_panel.py'


class FakeDesktop:
    def __init__(self, windows):
        self.windows = windows

    def EnumWindows(self, visit, user):
        for handle in self.windows:
            if not visit(handle, user):
                break

    def GetWindowThreadProcessId(self, hwnd, output):
        ctypes.cast(output, ctypes.POINTER(wintypes.DWORD)).contents.value = self.windows[hwnd]['pid']
        return 1

    def IsWindowVisible(self, hwnd):
        return self.windows[hwnd].get('visible', True)

    def GetWindowTextLengthW(self, hwnd):
        return len(self.windows[hwnd]['title'])

    def GetWindowTextW(self, hwnd, output, length):
        output.value = self.windows[hwnd]['title'][:length - 1]
        return len(output.value)

    def GetWindowLongPtrW(self, hwnd, index):
        assert index == win.GWL_EXSTYLE
        return self.windows[hwnd].get('exstyle', 0)

    def GetLayeredWindowAttributes(self, hwnd, color, alpha, flags):
        ctypes.cast(alpha, ctypes.POINTER(ctypes.c_ubyte)).contents.value = self.windows[hwnd].get('alpha', 0)
        return 1


def test_launch_only_may_find_transparent_non_taskbar_window(monkeypatch):
    monkeypatch.setattr(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE, raising=False)
    windows = {
        1: {'pid': 300, 'title': 'FRB Studio  起動中...'},
        2: {'pid': 301, 'title': 'FRB Studio / Native Shell'},
        3: {'pid': 300, 'title': 'FRB Studio / Native Shell',
            'exstyle': win.WS_EX_LAYERED, 'alpha': 0},
    }
    monkeypatch.setattr(win, '_user32', lambda: FakeDesktop(windows))
    assert win.find_studio_main_window(300) is None
    assert win.find_studio_main_window(300, launch_preview=True) == 3
    assert win.find_studio_main_window(301, launch_preview=True) == 2


def test_standalone_still_requires_visible_ready_main_window(monkeypatch):
    monkeypatch.setattr(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE, raising=False)
    windows = {
        3: {'pid': 300, 'title': 'FRB Studio / Native Shell', 'visible': False},
        4: {'pid': 300, 'title': 'FRB Studio / Native Shell',
            'exstyle': win.WS_EX_APPWINDOW | win.WS_EX_LAYERED, 'alpha': 20},
    }
    monkeypatch.setattr(win, '_user32', lambda: FakeDesktop(windows))
    assert win.find_studio_main_window(300) is None
    assert win.find_studio_main_window(300, launch_preview=True) == 4


def test_no_non_owned_pid_or_lookalike_window(monkeypatch):
    monkeypatch.setattr(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE, raising=False)
    windows = {
        3: {'pid': 301, 'title': 'FRB Studio / Native Shell'},
        4: {'pid': 300, 'title': 'FRB Studio / Native Shell — copy'},
    }
    monkeypatch.setattr(win, '_user32', lambda: FakeDesktop(windows))
    assert win.find_studio_main_window(300, launch_preview=True) is None


def method(name):
    tree = ast.parse(PANEL.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'StudioPreviewPanel')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(PANEL), 'exec'), scope)
    return scope[name]


def test_dock_ack_success_updates_pane_without_reparent_or_focus():
    trace = []
    obj = NS(_process=NS(pid=300), _studio_dock_pending=True,
             _attached=NS(attached=True),
             status_label=NS(hide=lambda: trace.append('hide'),
                             show=lambda: trace.append('show'),
                             setText=lambda msg: trace.append(msg)),
             _sync_popout_button=lambda: trace.append('button'))
    method('_on_studio_dock_completed')(obj, 300, 'OK')
    assert obj._studio_dock_pending is False
    assert trace == ['hide', 'button']


def test_old_process_ack_ignored_after_release():
    trace = []
    obj = NS(_process=NS(pid=600), _studio_dock_pending=True,
             _attached=NS(attached=True),
             status_label=NS(hide=lambda: trace.append('hide')),
             _sync_popout_button=lambda: trace.append('button'))
    method('_on_studio_dock_completed')(obj, 300, 'OK')
    assert obj._studio_dock_pending is True
    assert trace == []


def test_poll_has_explicit_hidden_preview_mode_and_dock_ack():
    text = PANEL.read_text(encoding='utf-8')
    assert 'find_studio_main_window(self._process.pid, launch_preview=True)' in text
    assert 'self._attached = AttachedStudioWindow(hwnd, int(self.host.winId()))' in text
    assert 'self._notify_studio_docked()' in text
    assert "channel.write(b'@FRB_LAUNCH_DOCKED@\\n')" in text
