"""Block Mouse Pointer Rod input while any opaque top-level window covers its pad.

Inspect the Win32 *z-order*, rather than only the foreground process.  An
always-on-top, non-activating window can cover the blue operating area while
FRB Launch remains the foreground application.
"""
from __future__ import annotations

from dataclasses import dataclass
import sys


@dataclass(frozen=True)
class WindowInZOrder:
    hwnd: int
    rect: tuple[int, int, int, int] | None
    visible: bool = True
    minimized: bool = False
    click_through: bool = False
    cloaked: bool = False


def rectangles_intersect(a, b) -> bool:
    """Half-open global pixel coordinates, matching Qt rect endpoints."""
    return (a[0] < b[2] and b[0] < a[2] and
            a[1] < b[3] and b[1] < a[3])


def is_uncovered_in_z_order(root_hwnd, pad_rect, windows, *, ignore_hwnds=()) -> bool:
    """Enumerate topmost first; stop at our own native top-level window.

    Do not treat an unknown/vanished owner as permission to inject input.
    Native input-transparent drawing overlays may be above the owning window.
    """
    if not root_hwnd or pad_rect[0] >= pad_rect[2] or pad_rect[1] >= pad_rect[3]:
        return False
    ignored = set(ignore_hwnds)
    for window in windows:
        if window.hwnd == root_hwnd:
            return True
        if (window.hwnd in ignored or not window.visible or window.minimized or
                window.cloaked or window.click_through):
            continue
        if window.rect is None or rectangles_intersect(pad_rect, window.rect):
            return False
    return False


def rod_area_uncovered(owner_hwnd: int, pad_rect: tuple[int, int, int, int],
                       *, ignore_hwnds=(), pad_client_rect=None,
                       owner_qt_size=None):
    """Return True if unobstructed, False if obstructed/unknown, None off Windows.

    WindowFromPoint alone would miss an overlap in a *different* part of the
    blue area.  Enumerating HWNDs above our native root catches partial
    overlaps too.  No activation, focus change or mouse injection is used.
    """
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
        user.ClientToScreen.restype = wintypes.BOOL
        user.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        user.GetClientRect.restype = wintypes.BOOL
        user.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        user.GetAncestor.restype = wintypes.HWND
        user.GetTopWindow.argtypes = (wintypes.HWND,)
        user.GetTopWindow.restype = wintypes.HWND
        user.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
        user.GetWindow.restype = wintypes.HWND
        user.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        user.GetWindowRect.restype = wintypes.BOOL
        user.IsWindowVisible.argtypes = (wintypes.HWND,)
        user.IsWindowVisible.restype = wintypes.BOOL
        user.IsIconic.argtypes = (wintypes.HWND,)
        user.IsIconic.restype = wintypes.BOOL
        user.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
        user.GetWindowLongW.restype = ctypes.c_long

        own_root = int(user.GetAncestor(int(owner_hwnd), 2) or 0)  # GA_ROOT
        if not own_root:
            return False
        if pad_client_rect is not None and owner_qt_size is not None:
            # Qt uses device-independent coordinates; DWM window bounds are
            # physical Win32 pixels.  Anchor and scale to the native client
            # rect so 125%/150% DPI and secondary screens compare like units.
            client = wintypes.RECT()
            origin = wintypes.POINT(0, 0)
            qt_width, qt_height = owner_qt_size
            if (qt_width <= 0 or qt_height <= 0 or
                    not user.GetClientRect(own_root, ctypes.byref(client)) or
                    not user.ClientToScreen(own_root, ctypes.byref(origin))):
                return False
            sx = (client.right - client.left) / qt_width
            sy = (client.bottom - client.top) / qt_height
            if sx <= 0 or sy <= 0:
                return False
            pad_rect = (origin.x + round(pad_client_rect[0] * sx),
                        origin.y + round(pad_client_rect[1] * sy),
                        origin.x + round(pad_client_rect[2] * sx),
                        origin.y + round(pad_client_rect[3] * sy))
        try:
            dwm = ctypes.WinDLL('dwmapi', use_last_error=True)
            dwm.DwmGetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD,
                                                  ctypes.c_void_p, wintypes.DWORD)
            dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        except OSError:
            dwm = None

        def window_entries():
            hwnd = int(user.GetTopWindow(None) or 0)
            visited = set()
            while hwnd and hwnd not in visited:
                visited.add(hwnd)
                if hwnd == own_root:
                    yield WindowInZOrder(hwnd, None)
                    return
                visible = bool(user.IsWindowVisible(hwnd))
                minimized = bool(user.IsIconic(hwnd))
                ex_style = int(user.GetWindowLongW(hwnd, -20))  # GWL_EXSTYLE
                click_through = bool(ex_style & 0x00000020)  # WS_EX_TRANSPARENT
                cloaked = False
                region = None
                if visible and not minimized and not click_through:
                    if dwm is not None:
                        state = wintypes.DWORD(0)
                        if dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(state),
                                                    ctypes.sizeof(state)) == 0:
                            cloaked = bool(state.value)
                    if not cloaked:
                        # DWM extended frame bounds exclude invisible resize borders.
                        r = wintypes.RECT()
                        if (dwm is not None and
                                dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r),
                                                          ctypes.sizeof(r)) == 0):
                            region = (r.left, r.top, r.right, r.bottom)
                        elif user.GetWindowRect(hwnd, ctypes.byref(r)):
                            region = (r.left, r.top, r.right, r.bottom)
                yield WindowInZOrder(hwnd, region, visible, minimized,
                                     click_through, cloaked)
                hwnd = int(user.GetWindow(hwnd, 2) or 0)  # GW_HWNDNEXT

        return is_uncovered_in_z_order(own_root, pad_rect, window_entries(),
                                       ignore_hwnds=ignore_hwnds)
    except (OSError, ValueError, RuntimeError, TypeError):
        return False  # Fail closed; a hidden input target must never react.
