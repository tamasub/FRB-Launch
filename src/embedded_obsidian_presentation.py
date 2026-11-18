"""Best-effort light native frame for a newly docked Obsidian HWND.

Electron's *inside* colors are owned by Obsidian's own theme: do not modify
vault appearance settings or a user process. The DWM frame hints alone may
not affect an app-drawn toolbar, and are intentionally failure-tolerant.
"""
import ctypes
import os


def prefer_light_native_frame(hwnd):
    if os.name != 'nt' or not hwnd:
        return False
    try:
        dwm = ctypes.WinDLL('dwmapi', use_last_error=True)
        off = ctypes.c_int(0)
        # Win11/Win10 20H1: prefer a light frame; older builds: ID 19.
        code = dwm.DwmSetWindowAttribute(ctypes.c_void_p(int(hwnd)), 20,
                                         ctypes.byref(off), ctypes.sizeof(off))
        if code != 0:
            code = dwm.DwmSetWindowAttribute(ctypes.c_void_p(int(hwnd)), 19,
                                             ctypes.byref(off), ctypes.sizeof(off))
        return code == 0
    except (OSError, ValueError, AttributeError):
        return False
