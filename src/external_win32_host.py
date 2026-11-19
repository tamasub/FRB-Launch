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
    u.GetWindowLongPtrW.argtypes = [h, ctypes.c_int]
    u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
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


def editor_windows(editor, *, include_hidden=False):
    """List (hwnd, pid, title) of titled editor top-level windows."""
    expected = {'obsidian': 'obsidian.exe', 'sakura': 'sakura.exe', 'vscode': 'code.exe'}.get(editor)
    if expected is None:
        return []
    user32, kernel = _api()
    items = []
    processes = {}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        # GetParent() also returns the OWNER of an ordinary top-level popup.
        # Sakura's tabbed editor can be an owned popup: excluding that HWND
        # silently skipped the consent prompt. Only reject true WS_CHILDs.
        if (not include_hidden and not user32.IsWindowVisible(hwnd)) or (
                int(user32.GetWindowLongPtrW(hwnd, -16)) & 0x40000000):
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


def pick_existing_sakura_window(windows):
    """Pick one visible editor HWND for EXPLICIT consent, never auto-adopt.

    EnumWindows yields top-level windows in z-order. Prefer an editor caption
    over auxiliary dialogs, but present that caption to the user before any
    SetParent call. Hidden/stale windows are excluded by the caller.
    """
    usable = [(hwnd, pid, title) for hwnd, pid, title in windows
              if hwnd and pid and str(title).strip()]
    if not usable:
        return None
    main = [(hwnd, pid, title) for hwnd, pid, title in usable
            if ('サクラエディタ' in title or 'sakura' in title.casefold())
            and not any(word in title.casefold() for word in
                        ('設定', '検索', '置換', 'ダイアログ', 'option', 'dialog', 'find', 'replace'))]
    return (main or usable)[0]


def snapshot_editor_windows(editor):
    # Include hidden desktop windows: they are not created by this Launch call.
    return frozenset(hwnd for hwnd, _pid, _title in editor_windows(editor, include_hidden=True))


def snapshot_editor_process_ids(editor):
    """Existing editor PIDs must not become Launch-owned by a new file-open."""
    return frozenset(pid for _hwnd, pid, _title in editor_windows(editor, include_hidden=True))


def editor_window_pid(hwnd):
    """Check the CURRENT process of an HWND, including when it is a Qt child."""
    user32, _kernel = _api()
    pid = wintypes.DWORD()
    if not hwnd:
        return 0
    user32.GetWindowThreadProcessId(int(hwnd), ctypes.byref(pid))
    return int(pid.value)


def editor_window_title(hwnd):
    """Read a Sakura HWND caption even after it was docked under a Qt parent.

    The top-level editor_windows() enumeration deliberately excludes children;
    a tab switch inside the *already embedded* Sakura HWND therefore needs a
    direct caption lookup. Do not activate, resize or reparent the window.
    """
    user32, _kernel = _api()
    handle = int(hwnd or 0)
    if not handle:
        return ''
    length = user32.GetWindowTextLengthW(handle)
    if length < 1:
        return ''
    title = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, title, length + 1)
    return title.value


def find_new_editor_window(target, previous, launched_pid=None, excluded_pids=None):
    """Refuse an existing editor window even if its title now matches target."""
    name = Path(target.path).name.casefold()
    stem = Path(target.path).stem.casefold()
    # A new *caption* on an existing editor process is NOT a new Launch-owned
    # editor. In particular, Sakura can reuse the user's already-open tabs.
    excluded = frozenset(excluded_pids or ())
    new = [(hwnd, pid, title) for hwnd, pid, title in editor_windows(target.app)
           if hwnd not in previous and pid not in excluded]
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
