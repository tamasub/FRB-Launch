"""Regression: Launch menu NativeShell has a different caption from Studio.

Run against the small Win32 HWND detection routine without requiring Windows.
Real cross-process docking/Save requires an on-device Windows acceptance test.
"""
import ctypes
from ctypes import wintypes

import pytest
import studio_win32_host as host


class WindowWorld:
    def __init__(self, windows):
        # hwnd => {pid, title, visible, style, alpha}
        self.windows = windows

    def EnumWindows(self, callback, unused):
        for hwnd in tuple(self.windows):
            if not callback(hwnd, unused):
                break

    def GetWindowThreadProcessId(self, hwnd, pid_pointer):
        ctypes.cast(pid_pointer, ctypes.POINTER(wintypes.DWORD)).contents.value = self.windows[hwnd]['pid']
        return 1

    def IsWindowVisible(self, hwnd):
        return self.windows[hwnd].get('visible', True)

    def GetWindowTextLengthW(self, hwnd):
        return len(self.windows[hwnd]['title'])

    def GetWindowTextW(self, hwnd, buffer, size):
        title = self.windows[hwnd]['title']
        buffer.value = title[:size - 1]
        return len(buffer.value)

    def GetWindowLongPtrW(self, hwnd, name):
        assert name == host.GWL_EXSTYLE
        return self.windows[hwnd].get('exstyle', host.WS_EX_APPWINDOW)

    def GetLayeredWindowAttributes(self, hwnd, color, alpha, flags):
        ctypes.cast(alpha, ctypes.POINTER(ctypes.c_ubyte)).contents.value = self.windows[hwnd].get('alpha', 255)
        return 1


def lookup(monkeypatch, entries, pid=123):
    monkeypatch.setattr(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE, raising=False)
    monkeypatch.setattr(host, '_user32', lambda: WindowWorld(entries))
    return host.find_studio_main_window(pid)


@pytest.mark.parametrize('caption', ['FRB Studio / Native Shell', 'FRB Launch — 設定'])
def test_both_native_shell_modes_can_dock(monkeypatch, caption):
    assert lookup(monkeypatch, {101: {'pid': 123, 'title': caption}}) == 101


def test_ignore_splash_and_unrelated_windows(monkeypatch):
    assert lookup(monkeypatch, {
        11: {'pid': 123, 'title': 'FRB Studio  起動中...'},
        12: {'pid': 456, 'title': 'FRB Launch — 設定'},
        13: {'pid': 123, 'title': 'Notepad'},
        14: {'pid': 123, 'title': 'FRB Launch — 設定 (copy)'},
    }) is None


def test_wait_until_launch_shell_revealed(monkeypatch):
    assert lookup(monkeypatch, {
        30: {'pid': 123, 'title': 'FRB Launch — 設定', 'exstyle': 0},
    }) is None
    assert lookup(monkeypatch, {
        30: {'pid': 123, 'title': 'FRB Launch — 設定',
             'exstyle': host.WS_EX_APPWINDOW | host.WS_EX_LAYERED, 'alpha': 0},
    }) is None
    assert lookup(monkeypatch, {
        30: {'pid': 123, 'title': 'FRB Launch — 設定',
             'exstyle': host.WS_EX_APPWINDOW | host.WS_EX_LAYERED, 'alpha': 255},
    }) == 30


def test_hidden_launch_settings_not_eligible(monkeypatch):
    assert lookup(monkeypatch, {
        33: {'pid': 123, 'title': 'FRB Launch — 設定', 'visible': False},
    }) is None
