"""Protect native third-column guests during minimize/restore transitions.

Never terminate a process or send WM_CLOSE: it may own unsaved documents.
Only call these helpers for a previously verified, Launch-managed HWND.
"""
import ctypes
import os

SW_SHOWMINNOACTIVE = 7  # Window is minimized without taking input focus.
SW_SHOWNOACTIVATE = 4  # Restore its normal placement without focus stealing.


def _user32():
    if os.name != 'nt':
        raise OSError('Windows native window operations require Windows')
    return ctypes.windll.user32


def park_native_window(hwnd, *, user32=None):
    """Minimize a still-live HWND; never infer process lifetime from it."""
    u = user32 if user32 is not None else _user32()
    hwnd = int(hwnd)
    if not hwnd or not u.IsWindow(hwnd):
        return False
    u.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
    return bool(u.IsWindow(hwnd) and u.IsIconic(hwnd))


def prepare_native_redock(hwnd, *, user32=None):
    """Unminimize before attaching to a desktop-positioned overlay/Qt host."""
    u = user32 if user32 is not None else _user32()
    hwnd = int(hwnd)
    if not hwnd or not u.IsWindow(hwnd):
        return False
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    return bool(u.IsWindow(hwnd) and not u.IsIconic(hwnd))
