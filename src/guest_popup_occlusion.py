"""Allow Launch's in-process popup panels to cover a top-level guest overlay.

A floating Obsidian/VS Code-style guest is NOT a child of Launch: Qt's
QFrame.raise_() cannot put a history/favorites popup over the guest HWND.
Instead of hiding/reparenting the guest (which breaks IME or makes the third
column blank), cut only the popup-covered pixels out of its Win32 window region.

All geometry conversion is side-effect free; the optional native mask owns
its GDI regions and resets them when popups close or the guest detaches.
"""
import ctypes
import math
import os
from ctypes import wintypes

RGN_DIFF = 4


def popup_cutouts(physical_size, logical_size, logical_popup_rects, *, margin=2):
    """Return clipped guest-local physical rectangles to expose Launch popups.

    ``logical_popup_rects`` are (x, y, width, height) in the Qt host's local
    *logical* coordinates.  The guest/host physical pixel rectangle comes
    from Win32 ClientToScreen/GetClientRect, not Qt's global logical position.
    This handles Windows DPI scaling and even popups extending to the left of
    the third column.  No popup content, names or filesystem data is needed.
    """
    try:
        pw, ph = map(int, physical_size)
        qw, qh = map(float, logical_size)
    except (ValueError, TypeError):
        return ()
    if pw < 1 or ph < 1 or qw <= 0 or qh <= 0:
        return ()
    fx, fy = pw / qw, ph / qh
    cuts = set()
    for values in logical_popup_rects or ():
        try:
            x, y, w, h = map(float, values)
        except (ValueError, TypeError):
            continue
        if not all(map(math.isfinite, (x, y, w, h))) or w <= 0 or h <= 0:
            continue
        left = max(0, math.floor(x * fx) - margin)
        top = max(0, math.floor(y * fy) - margin)
        right = min(pw, math.ceil((x + w) * fx) + margin)
        bottom = min(ph, math.ceil((y + h) * fy) + margin)
        if left < right and top < bottom:
            cuts.add((left, top, right, bottom))
    return tuple(sorted(cuts))


class NativePopupMask:
    """Win32 SetWindowRgn adapter; no-op unless an overlap must be masked.

    Ownership: after successful SetWindowRgn Windows owns the region handle;
    never DeleteObject it.  On failure all GDI handles are released locally.
    """

    def __init__(self, user32, guest_hwnd, *, gdi32=None):
        self.u = user32
        self.hwnd = int(guest_hwnd)
        self.gdi = gdi32
        self._key = None
        self._supported = True

    def _load_api(self):
        if self.gdi is None:
            if os.name != 'nt':
                return False
            self.gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        if not hasattr(self.u, 'SetWindowRgn'):
            return False
        signature = (
            (self.gdi.CreateRectRgn, [ctypes.c_int] * 4, wintypes.HRGN),
            (self.gdi.CombineRgn, [wintypes.HRGN] * 3 + [ctypes.c_int], ctypes.c_int),
            (self.gdi.DeleteObject, [wintypes.HGDIOBJ], wintypes.BOOL),
            (self.u.SetWindowRgn, [wintypes.HWND, wintypes.HRGN, wintypes.BOOL], ctypes.c_int),
        )
        for fn, args, result in signature:
            try:
                fn.argtypes = args
                fn.restype = result
            except AttributeError:  # Python fake Win32 methods in tests
                pass
        return True

    def apply(self, physical_size, cuts):
        cuts = tuple(cuts or ())
        if not cuts:
            return self.clear()
        key = (tuple(physical_size), cuts)
        if self._key == key:
            return True
        if not self._supported:
            return False
        if not self._load_api():
            self._supported = False
            return False
        width, height = map(int, physical_size)
        base = self.gdi.CreateRectRgn(0, 0, width, height)
        if not base:
            return False
        transferred = False
        try:
            for x0, y0, x1, y1 in cuts:
                hole = self.gdi.CreateRectRgn(x0, y0, x1, y1)
                if not hole:
                    return False
                try:
                    if self.gdi.CombineRgn(base, base, hole, RGN_DIFF) == 0:
                        return False
                finally:
                    self.gdi.DeleteObject(hole)
            if not self.u.SetWindowRgn(self.hwnd, base, True):
                return False
            transferred = True  # Windows owns `base` from this point.
            self._key = key
            return True
        finally:
            if not transferred:
                self.gdi.DeleteObject(base)

    def clear(self):
        if self._key is None:
            return True
        if not self.u.SetWindowRgn(self.hwnd, 0, True):
            return False
        self._key = None
        return True
