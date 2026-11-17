"""Find *newly opened* external editor HWNDs without stealing existing work.

Only new normal top-level windows of the exact editor executable qualify;
file-name title matching additionally prevents accidental docking of splash,
settings and unrelated newly created windows. Failure always leaves the editor
window as a standalone window rather than modifying an unrelated HWND.
"""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _api():
    if os.name != 'nt':
        raise OSError('外部ウィンドウの収容はWindows専用です')
    u = ctypes.WinDLL('user32', use_last_error=True)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    h = wintypes.HWND
    u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, h, wintypes.LPARAM), wintypes.LPARAM]
    u.GetWindowThreadProcessId.argtypes = [h, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetWindowTextLengthW.argtypes = [h]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [h, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.IsWindowVisible.argtypes = [h]
    u.IsWindowVisible.restype = wintypes.BOOL
    u.GetParent.argtypes = [h]
    u.GetParent.restype = h
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                             wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.QueryFullProcessImageNameW.restype = wintypes.BOOL
    return u, k


def _process_name(kernel, pid):
    process = kernel.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not process:
        return ''
    try:
        size = wintypes.DWORD(32768)
        filename = ctypes.create_unicode_buffer(size.value)
        if kernel.QueryFullProcessImageNameW(process, 0, filename, ctypes.byref(size)):
            return filename.value.replace('/', '\\').rsplit('\\', 1)[-1].casefold()
        return ''
    finally:
        kernel.CloseHandle(process)


def editor_windows(editor):
    """List (hwnd, pid, title) of visible, titled editor top-level windows."""
    expected = {'obsidian': 'obsidian.exe', 'sakura': 'sakura.exe'}.get(editor)
    if expected is None:
        return []
    user32, kernel = _api()
    items = []
    processes = {}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetParent(hwnd):
            return True
        count = user32.GetWindowTextLengthW(hwnd)
        if count < 2:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in processes:
            processes[pid.value] = _process_name(kernel, pid.value)
        if processes[pid.value] != expected:
            return True
        title = ctypes.create_unicode_buffer(count + 1)
        user32.GetWindowTextW(hwnd, title, count + 1)
        items.append((int(hwnd), int(pid.value), title.value))
        return True

    user32.EnumWindows(visit, 0)
    return items


def snapshot_editor_windows(editor):
    return frozenset(hwnd for hwnd, _pid, _title in editor_windows(editor))


def find_new_editor_window(target, previous, launched_pid=None):
    """Refuse an existing editor window even if its title now matches target."""
    name = Path(target.path).name.casefold()
    stem = Path(target.path).stem.casefold()
    new = [(hwnd, pid, title) for hwnd, pid, title in editor_windows(target.app)
           if hwnd not in previous]
    titled = [(hwnd, pid) for hwnd, pid, title in new
              if name in title.casefold() or stem in title.casefold()]
    if len(titled) == 1:
        return titled[0][0]
    # Sakura may use a customized document caption. Restrict fallback to the
    # exact newly spawned process and a unique HWND; Obsidian has no such fallback.
    if target.app == 'sakura' and launched_pid:
        matching = [(hwnd, pid) for hwnd, pid, _title in new if pid == launched_pid]
        if len(matching) == 1:
            return matching[0][0]
    return None
