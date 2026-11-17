"""Obsidian embedded native focus handoff: safe Win32 boundaries (no Qt required).

The last step (physical keyboard input in a cross-process Electron renderer)
needs a Windows GUI smoke test; these tests verify click-only focus and guardrails.
"""
import ast
import ctypes
import sys
import types
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import desktop_double_click
from desktop_double_click import DesktopDoubleClick, LowLevelMouseInfo
from studio_win32_host import focus_embedded_editor_from_click

SRC = Path(__file__).resolve().parents[1] / 'src'


class FakeWindows:
    def __init__(self, *, hit=101, root=777, foreground=777,
                 child=True, attached=True, focused=True):
        self.hit, self.root, self.foreground = hit, root, foreground
        self.child, self.attached, self.focused = child, attached, focused
        self.calls = []
        self.focus = 999

    def IsWindow(self, hwnd):
        return hwnd in (100, 101, 102, 200, 777, 999)

    def WindowFromPoint(self, point):
        self.calls.append(('hit', point.x, point.y))
        return self.hit

    def IsChild(self, parent, child):
        return self.child and parent == 100 and child == 101

    def GetAncestor(self, hwnd, flag):
        self.calls.append(('root', hwnd, flag))
        return self.root

    def GetForegroundWindow(self):
        return self.foreground

    def GetWindowThreadProcessId(self, hwnd, pid):
        return 222

    def AttachThreadInput(self, a, b, enable):
        self.calls.append(('attach', a, b, bool(enable)))
        return self.attached

    def SetFocus(self, hwnd):
        self.calls.append(('focus', hwnd))
        if self.focused:
            self.focus = hwnd
        return 999

    def GetFocus(self):
        return self.focus


def focus(api, x=10, y=20):
    return focus_embedded_editor_from_click(
        100, 200, x, y, user32=api, get_current_thread_id=lambda: 111)


def test_inside_click_moves_native_focus_and_releases_foreign_input_thread():
    api = FakeWindows()
    assert focus(api)
    assert ('focus', 101) in api.calls
    assert ('attach', 111, 222, True) in api.calls
    assert api.calls[-1] == ('attach', 111, 222, False)
    assert not any(call[0] in ('kill', 'send_keys', 'activate_desktop') for call in api.calls)


def test_click_elsewhere_never_steals_focus():
    for variant in ({'hit': 102}, {'child': False}, {'foreground': 888},
                    {'root': 0}, {'attached': False}):
        api = FakeWindows(**variant)
        assert not focus(api), variant
        assert ('focus', 101) not in api.calls


def test_existing_electron_focus_and_caret_are_not_overwritten():
    api = FakeWindows()
    api.focus = 101
    assert focus(api)
    assert ('focus', 101) not in api.calls
    assert api.calls[-1] == ('attach', 111, 222, False)


def test_focus_failure_still_detaches_input_queues():
    api = FakeWindows(focused=False)
    assert not focus(api)
    assert api.calls[-1] == ('attach', 111, 222, False)


def test_native_mouse_hook_schedules_only_on_left_button_release():
    called, scheduled = [], []
    timer = types.ModuleType('PySide6.QtCore')
    timer.QTimer = SimpleNamespace(singleShot=lambda delay, func: scheduled.append(func))
    parent = types.ModuleType('PySide6')
    parent.QtCore = timer

    class HookUser:
        def CallNextHookEx(self, *args):
            return 0

    api = DesktopDoubleClick.__new__(DesktopDoubleClick)
    api.user = HookUser()
    api.hook = 1
    api.logger = None
    api.on_embedded_mouse_release = lambda x, y: called.append((x, y))
    api.outside_guard = SimpleNamespace(blocks_open=lambda tick: True)
    api.pair = SimpleNamespace(previous=None)
    api.raw_pair = SimpleNamespace(previous=None)
    api.is_launcher_visible = lambda: False
    api.on_outside_click = None
    info = LowLevelMouseInfo()
    info.pt.x, info.pt.y, info.time = 320, 450, 1000
    with patch.dict(sys.modules, {'PySide6': parent, 'PySide6.QtCore': timer}):
        api._mouse(0, DesktopDoubleClick.WM_LBUTTONUP, ctypes.addressof(info))
        assert called == []  # Never do Win32 activation inside low-level hook.
        assert len(scheduled) == 1
        scheduled.pop()()
        assert called == [(320, 450)]
        api._mouse(0, DesktopDoubleClick.WM_RBUTTONDOWN, ctypes.addressof(info))
        assert not scheduled


def test_preview_handoff_alias_uses_shared_sakura_obsidian_focus():
    node = ast.parse((SRC / 'studio_preview_panel.py').read_text(encoding='utf-8'))
    klass = next(t for t in node.body if isinstance(t, ast.ClassDef)
                 and t.name == 'StudioPreviewPanel')
    method = next(t for t in klass.body if isinstance(t, ast.FunctionDef)
                  and t.name == 'focus_obsidian_after_native_click')
    exec_ns = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'method', 'exec'), exec_ns)
    f = exec_ns[method.name]
    calls = []
    panel = SimpleNamespace(focus_external_after_native_click=lambda x, y: calls.append((x, y)) or True)
    assert f(panel, 10, 20) is True
    assert calls == [(10, 20)]

