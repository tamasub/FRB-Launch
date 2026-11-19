"""Best-effort early capture of a NEW Obsidian pop-out during Launch docking.

Obsidian is an external Electron app: Launch cannot prevent it from ever
showing a window.  A short-lived WinEvent listener can hide only a newly
created, positively identified note window as soon as Windows reports SHOW or
NAMECHANGE.  Polling remains a fallback.  Never touch windows in the initial
snapshot, unrelated processes, or dialogs without the note in their title.

An intercepted window is ALWAYS made visible again if docking fails, the user
exits, or the listener is otherwise abandoned. This module does not close
processes, send keys, or change Obsidian settings.
"""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path

_EVENT_OBJECT_SHOW = 0x8002
_EVENT_OBJECT_NAMECHANGE = 0x800C
_OBJID_WINDOW = 0
_CHILDID_SELF = 0
_WINEVENT_OUTOFCONTEXT = 0
_WINEVENT_SKIPOWNPROCESS = 0x0002
_WS_CHILD = 0x40000000
_SW_HIDE = 0
_SW_SHOWNOACTIVATE = 4
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _note_title_matches(title, note):
    """Exact note name or stem substring, matching existing HWND discovery."""
    title = str(title or '').casefold()
    name = Path(note).name.casefold()
    stem = Path(note).stem.casefold()
    return bool(title and ((name and name in title) or (stem and stem in title)))


class _WindowsEvents:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('Obsidianの早期ウィンドウ検出はWindows専用です')
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.callback_type = ctypes.WINFUNCTYPE(
            None, ctypes.c_void_p, wintypes.DWORD, wintypes.HWND,
            ctypes.c_long, ctypes.c_long, wintypes.DWORD, wintypes.DWORD)
        u = self.user
        u.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD,
                                       ctypes.c_void_p, self.callback_type,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        u.SetWinEventHook.restype = ctypes.c_void_p
        u.UnhookWinEvent.argtypes = [ctypes.c_void_p]
        u.UnhookWinEvent.restype = wintypes.BOOL
        u.IsWindow.argtypes = [wintypes.HWND]
        u.IsWindow.restype = wintypes.BOOL
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.IsWindowVisible.restype = wintypes.BOOL
        u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextLengthW.restype = ctypes.c_int
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowTextW.restype = ctypes.c_int
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.ShowWindow.restype = wintypes.BOOL
        k = self.kernel
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                 wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._callback = None
        self._hooks = []

    def start(self, callback):
        self._callback = self.callback_type(callback)  # native callback must stay alive
        flags = _WINEVENT_OUTOFCONTEXT | _WINEVENT_SKIPOWNPROCESS
        for event in (_EVENT_OBJECT_SHOW, _EVENT_OBJECT_NAMECHANGE):
            hook = self.user.SetWinEventHook(event, event, None, self._callback, 0, 0, flags)
            if hook:
                self._hooks.append(hook)
        if not self._hooks:
            self._callback = None
            return False
        return True

    def stop(self):
        for hook in self._hooks:
            self.user.UnhookWinEvent(hook)
        self._hooks.clear()
        self._callback = None

    def matches(self, hwnd, note):
        u = self.user
        if not u.IsWindow(hwnd) or (int(u.GetWindowLongPtrW(hwnd, -16)) & _WS_CHILD):
            return False
        length = u.GetWindowTextLengthW(hwnd)
        if length < 2:
            return False
        title = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(hwnd, title, length + 1)
        if not _note_title_matches(title.value, note):
            return False
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False
        process = self.kernel.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not process:
            return False
        try:
            size = wintypes.DWORD(32768)
            name = ctypes.create_unicode_buffer(size.value)
            if not self.kernel.QueryFullProcessImageNameW(process, 0, name, ctypes.byref(size)):
                return False
            return name.value.replace('/', '\\').rsplit('\\', 1)[-1].casefold() == 'obsidian.exe'
        finally:
            self.kernel.CloseHandle(process)

    def hide(self, hwnd):
        if not self.user.IsWindow(hwnd):
            return False
        self.user.ShowWindow(hwnd, _SW_HIDE)
        return True

    def reveal(self, hwnd):
        if self.user.IsWindow(hwnd) and not (int(self.user.GetWindowLongPtrW(hwnd, -16)) & _WS_CHILD):
            self.user.ShowWindow(hwnd, _SW_SHOWNOACTIVATE)


class ObsidianQuietHandoff:
    """One URI request, one short-lived watcher. Never adopts desktop HWNDs."""
    def __init__(self, note, baseline_hwnds, on_captured, *, backend=None):
        self.note = str(note)
        self.baseline = frozenset(int(h) for h in baseline_hwnds)
        self.on_captured = on_captured
        self.backend = backend
        self.hidden_hwnds = set()
        self.active = False

    def start(self):
        if self.active:
            return True
        try:
            self.backend = self.backend or _WindowsEvents()
            self.active = bool(self.backend.start(self._on_window_event))
        except (OSError, ValueError, RuntimeError):
            self.active = False
        return self.active

    def _on_window_event(self, hook, event, hwnd, obj_id, child_id, thread, tick):
        if (not self.active or int(event) not in (_EVENT_OBJECT_SHOW, _EVENT_OBJECT_NAMECHANGE)
                or obj_id != _OBJID_WINDOW or child_id != _CHILDID_SELF):
            return
        handle = int(hwnd or 0)
        if not handle or handle in self.baseline or handle in self.hidden_hwnds:
            return
        try:
            if not self.backend.matches(handle, self.note):
                return
            if not self.backend.hide(handle):
                return
            self.hidden_hwnds.add(handle)
            # Delivery is on Qt's window-message thread. Queue a native HWND
            # scan immediately; do NOT SetParent from inside the WinEvent hook.
            self.on_captured()
        except (OSError, RuntimeError, ValueError):
            return  # 50ms poll continues to provide the normal fallback

    def stop(self, *, restore=False):
        """Return captured desktop windows if we couldn't dock them."""
        if self.backend is not None:
            try:
                self.backend.stop()
            except (OSError, RuntimeError):
                pass
            if restore:
                for hwnd in tuple(self.hidden_hwnds):
                    try:
                        self.backend.reveal(hwnd)
                    except (OSError, RuntimeError):
                        pass
        self.active = False
        self.hidden_hwnds.clear()
