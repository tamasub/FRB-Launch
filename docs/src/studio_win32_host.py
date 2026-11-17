"""EXPERIMENTAL: dock an already running FRB Studio WinForms window in Qt.

No file reads/writes occur here: Studio's WebView2 + C# NativeShell remain the
only editors and save authorities. Every docked window is restored to a normal
standalone window before the Qt child host is hidden/destroyed. Windows only.
"""
import ctypes
import os
from ctypes import wintypes

WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_APPWINDOW = 0x00040000
SW_HIDE, SW_SHOWNOACTIVATE, SW_SHOW, SW_RESTORE = 0, 4, 5, 9
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def _user32():
    if os.name != 'nt':
        raise OSError('Studio第3列はWindows専用の実験機能です')
    u = ctypes.WinDLL('user32', use_last_error=True)
    h = wintypes.HWND
    u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, h, wintypes.LPARAM), wintypes.LPARAM]
    u.GetWindowThreadProcessId.argtypes = [h, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetWindowTextLengthW.argtypes = [h]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [h, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.IsWindow.argtypes = [h]
    u.IsWindow.restype = wintypes.BOOL
    u.IsWindowVisible.argtypes = [h]
    u.IsWindowVisible.restype = wintypes.BOOL
    u.GetParent.argtypes = [h]
    u.GetParent.restype = h
    u.SetParent.argtypes = [h, h]
    u.SetParent.restype = h
    u.GetWindowLongPtrW.argtypes = [h, ctypes.c_int]
    u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.SetWindowLongPtrW.argtypes = [h, ctypes.c_int, ctypes.c_ssize_t]
    u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.ShowWindow.argtypes = [h, ctypes.c_int]
    u.MoveWindow.argtypes = [h, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    u.MoveWindow.restype = wintypes.BOOL
    u.SetWindowPos.argtypes = [h, h, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u.SetWindowPos.restype = wintypes.BOOL
    u.GetWindowRect.argtypes = [h, ctypes.POINTER(wintypes.RECT)]
    u.GetWindowRect.restype = wintypes.BOOL
    u.GetLayeredWindowAttributes.argtypes = [h, ctypes.POINTER(wintypes.DWORD),
                                             ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(wintypes.DWORD)]
    u.GetLayeredWindowAttributes.restype = wintypes.BOOL
    u.SetForegroundWindow.argtypes = [h]
    u.PostMessageW.argtypes = [h, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.PostMessageW.restype = wintypes.BOOL
    return u


# Normal Studio and Launch maintenance are the same NativeShell executable.
# NativeShellForm.ApplyNativePresentation switches the caption for Launch
# settings once its launch ViewDef has loaded; keep both exact (not prefix)
# matches so the splash or unrelated windows are never embedded.
STUDIO_MAIN_CAPTIONS = frozenset((
    'FRB Studio / Native Shell',
    'FRB Launch — 設定',
))


def find_studio_main_window(pid):
    """Match either ready NativeShell caption, never the separate splash."""
    u = _user32()
    result = []
    cb_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @cb_type
    def visit(hwnd, _):
        target_pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
        if target_pid.value != pid or not u.IsWindowVisible(hwnd):
            return True
        size = u.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(size + 1)
        u.GetWindowTextW(hwnd, title, size + 1)
        if title.value in STUDIO_MAIN_CAPTIONS:
            # Studio shows its main form with Opacity=0 while the splash is up.
            # It also changes ShowInTaskbar at RevealMainWindow (which may
            # recreate the HWND). Attach ONLY after the WebView bridge is ready.
            exstyle = int(u.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))
            if not (exstyle & WS_EX_APPWINDOW):
                return True
            if exstyle & WS_EX_LAYERED:
                key = wintypes.DWORD()
                alpha = ctypes.c_ubyte()
                flags = wintypes.DWORD()
                if u.GetLayeredWindowAttributes(hwnd, ctypes.byref(key),
                                                 ctypes.byref(alpha), ctypes.byref(flags)):
                    if alpha.value < 200:
                        return True
            result.append(int(hwnd))
            return False
        return True

    u.EnumWindows(visit, 0)
    return result[0] if result else None


class AttachedStudioWindow:
    """One reversible cross-process HWND attachment; no process termination."""

    def __init__(self, hwnd, host_hwnd):
        self.u = _user32()
        self.hwnd = int(hwnd)
        self.host_hwnd = int(host_hwnd)
        if not self.u.IsWindow(self.hwnd) or not self.u.IsWindow(self.host_hwnd):
            raise OSError('Studioまたは第3列のウィンドウが無効です')
        self.original_style = int(self.u.GetWindowLongPtrW(self.hwnd, GWL_STYLE))
        self.original_parent = int(self.u.GetParent(self.hwnd) or 0)
        rect = wintypes.RECT()
        self.u.GetWindowRect(self.hwnd, ctypes.byref(rect))
        self.original_rect = (int(rect.left), int(rect.top),
                              max(320, int(rect.right - rect.left)),
                              max(240, int(rect.bottom - rect.top)))
        self.attached = False
        try:
            new_style = (self.original_style | WS_CHILD) & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME |
                         WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
            self.u.SetWindowLongPtrW(self.hwnd, GWL_STYLE, new_style)
            ctypes.set_last_error(0)
            self.u.SetParent(self.hwnd, self.host_hwnd)
            error = ctypes.get_last_error()
            if error:
                raise ctypes.WinError(error)
            self.attached = True
            self.resize(700, 500)
            self.u.ShowWindow(self.hwnd, SW_SHOW)
        except Exception:
            # A failed SetParent can leave the source window borderless even
            # when no child relationship was established. Always restore it.
            self.u.SetParent(self.hwnd, self.original_parent)
            self.u.SetWindowLongPtrW(self.hwnd, GWL_STYLE, self.original_style)
            x, y, w, h = self.original_rect
            self.u.SetWindowPos(self.hwnd, 0, x, y, w, h,
                                SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
            self.u.ShowWindow(self.hwnd, SW_SHOW)
            self.attached = False
            raise

    def resize(self, width, height):
        if self.attached and self.u.IsWindow(self.hwnd):
            w, h = max(1, int(width)), max(1, int(height))
            self.u.SetWindowPos(self.hwnd, 0, 0, 0, w, h,
                                SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def detach(self, *, foreground=False, show_window=True):
        """Restore native parent/style; optionally park the window hidden.

        show_window=False keeps an unsaved session alive without a desktop
        pop-out when the user switches documents in Launch's third column.
        """
        if not self.u.IsWindow(self.hwnd):
            self.attached = False
            return
        if self.attached:
            self.u.ShowWindow(self.hwnd, SW_HIDE)
            self.u.SetParent(self.hwnd, self.original_parent)
            self.u.SetWindowLongPtrW(self.hwnd, GWL_STYLE, self.original_style)
            x, y, w, h = self.original_rect
            self.u.SetWindowPos(self.hwnd, 0, x, y, w, h,
                                SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        self.attached = False
        if not show_window:
            self.u.ShowWindow(self.hwnd, SW_HIDE)
        elif foreground:
            self.u.ShowWindow(self.hwnd, SW_RESTORE)
            self.u.SetForegroundWindow(self.hwnd)
        else:
            self.u.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)


def restore_parked_studio_window(hwnd):
    """Unhide a previously detached Studio without altering its saved state."""
    u = _user32()
    if u.IsWindow(int(hwnd)):
        u.ShowWindow(int(hwnd), SW_SHOWNOACTIVATE)


def request_editor_window_close(hwnd):
    """Gracefully ask ONLY the captured external HWND to close.

    WM_CLOSE lets the editor prompt for saving unsaved documents. Never use
    TerminateProcess or kill by executable name: Sakura tabs and Obsidian
    vaults may share a process with the user's other work.
    """
    u = _user32()
    window = int(hwnd)
    if not u.IsWindow(window):
        return True
    if not u.PostMessageW(window, 0x0010, 0, 0):  # WM_CLOSE
        raise OSError('外部エディターへ通常終了要求を送れませんでした')
    return True
