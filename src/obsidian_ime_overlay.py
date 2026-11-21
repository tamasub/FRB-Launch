"""EXPERIMENTAL, OPT-IN: position Obsidian over the third column without SetParent.

Cross-process parenting of Chromium/Electron can make Windows TSF/IME report
candidate/inline composition windows at desktop (0,0).  This test keeps the
Obsidian HWND as a *top-level* window and aligns it to the native Qt host.

The Obsidian/VS Code window policy is unchanged. Sakura uses the same
non-parenting positioning while retaining its original Win32 styles.
On failure/parking/exit any changed window styles are restored.
This is an experiment, not a guarantee: other apps or dialogs may overlap it.
"""
import ctypes
import os
import atexit
from weakref import WeakSet
from ctypes import wintypes
from guest_popup_occlusion import NativePopupMask

from studio_win32_host import (
    _user32, WS_CHILD, WS_POPUP, WS_CAPTION, WS_THICKFRAME, WS_SYSMENU,
    WS_MINIMIZEBOX, WS_MAXIMIZEBOX, GWL_STYLE, GWL_EXSTYLE,
    WS_EX_APPWINDOW, SW_HIDE, SW_SHOWNOACTIVATE, SWP_NOACTIVATE,
    SWP_FRAMECHANGED,
)

WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
_LIVE_OVERLAYS = WeakSet()


def _restore_overlays_on_clean_exit():
    # Normal Qt shutdown normally detaches first; this handles early normal
    # Python process exit. A forced OS termination cannot run Python cleanup.
    for overlay in tuple(_LIVE_OVERLAYS):
        try:
            if overlay.attached:
                overlay.detach(foreground=False, show_window=True)
        except Exception:
            pass


atexit.register(_restore_overlays_on_clean_exit)
GA_ROOT = 2
GW_HWNDPREV = 3
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040


def overlay_enabled():
    """Use state.ini first; only use the legacy trial flag if unconfigured.

    The shipped defaults/state.ini seeds the initial user state.ini.  Explicit
    user state always wins over diagnostic batch flags, for all four editors.
    """
    from third_column_host_options import configured_embedded_editor
    configured = configured_embedded_editor(None, 'obsidian')
    if configured is not None:
        return configured
    trial = os.environ.get('FRB_OBSIDIAN_IME_OVERLAY')
    return trial is not None and trial.strip() == '1'


class ObsidianImeOverlay:
    """Reversible *non-parenting* top-level overlay with attachment API parity.

    Call sync() while the panel is active, including after window moves.
    No SetParent/IME context manipulation and never closes/kills Obsidian.
    """
    is_ime_overlay = True
    # Chrome/Electron guests use a client-drawn titlebar.  Native Win32
    # editors can override this policy without altering the overlay geometry.
    native_frame_on_attach = False
    # Sakura's classic Win32/GDI editor repaints its document and toolbars
    # based on its original top-level styles. Its guest must NOT be converted
    # to a popup/tool window. Electron guests keep their established policy.
    preserve_native_styles = False

    def _overlay_window_style(self):
        return ((self.original_style | WS_POPUP) &
                ~(WS_CHILD | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU |
                  WS_MINIMIZEBOX | WS_MAXIMIZEBOX))

    def __init__(self, hwnd, host_hwnd, *, user32=None):
        self.u = user32 if user32 is not None else _user32()
        self.hwnd, self.host_hwnd = int(hwnd), int(host_hwnd)
        self.attached = False
        self._visible = False
        self._last_rect = None
        self._popup_mask = NativePopupMask(self.u, self.hwnd)
        self._popup_hwnds = ()
        self._qt_host_size = None
        self._last_sync_foreground = None
        if not self.u.IsWindow(self.hwnd) or not self.u.IsWindow(self.host_hwnd):
            raise OSError('Obsidianまたは第3列のウィンドウが無効です')
        self._configure_api()
        self.original_style = int(self.u.GetWindowLongPtrW(self.hwnd, GWL_STYLE))
        if self.original_style & WS_CHILD:
            raise OSError('既に子ウィンドウ化されたObsidianには非親子化モードを使えません')
        self.original_exstyle = int(self.u.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE))
        old = wintypes.RECT()
        if not self.u.GetWindowRect(self.hwnd, ctypes.byref(old)):
            raise OSError('Obsidianの元の画面位置が取得できません')
        self.original_rect = (int(old.left), int(old.top),
                              max(1, int(old.right - old.left)),
                              max(1, int(old.bottom - old.top)))
        try:
            # No WS_CHILD and NO SetParent: Chromium keeps a top-level root
            # window for its original TSF / IME coordinate calculations.
            if not self.preserve_native_styles:
                style = self._overlay_window_style()
                exstyle = ((self.original_exstyle | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
                self.u.ShowWindow(self.hwnd, SW_HIDE)
                self.u.SetWindowLongPtrW(self.hwnd, GWL_STYLE, style)
                self.u.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, exstyle)
            # Native Sakura remains an ordinary top-level window, including
            # caption, frame, extended styles and its GDI child hierarchy.
            self.attached = True
            _LIVE_OVERLAYS.add(self)
            self.sync()
        except Exception:
            self._restore_original(show_window=True)
            raise

    def _configure_api(self):
        # ctypes declares only the signatures needed by this experiment.
        if hasattr(self.u, 'ClientToScreen'):
            self.u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            self.u.ClientToScreen.restype = wintypes.BOOL
        if hasattr(self.u, 'GetClientRect'):
            self.u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            self.u.GetClientRect.restype = wintypes.BOOL
        if hasattr(self.u, 'IsIconic'):
            self.u.IsIconic.argtypes = [wintypes.HWND]
            self.u.IsIconic.restype = wintypes.BOOL
        if hasattr(self.u, 'GetWindow'):
            self.u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
            self.u.GetWindow.restype = wintypes.HWND

    def _desktop_rect(self):
        rect = wintypes.RECT()
        point = wintypes.POINT(0, 0)
        if not self.u.GetClientRect(self.host_hwnd, ctypes.byref(rect)):
            return None
        if not self.u.ClientToScreen(self.host_hwnd, ctypes.byref(point)):
            return None
        return (int(point.x), int(point.y),
                max(1, int(rect.right - rect.left)),
                max(1, int(rect.bottom - rect.top)))

    def _root_hwnd(self):
        return int(self.u.GetAncestor(self.host_hwnd, GA_ROOT) or 0)

    def _root_is_topmost(self, root):
        return bool(int(self.u.GetWindowLongPtrW(root, GWL_EXSTYLE)) & WS_EX_TOPMOST)

    def _window_above_launch(self, root):
        # GW_HWNDPREV is the sibling IMMEDIATELY above Launch in the desktop
        # Z-order (not the active app). This makes a partially overlapping
        # Chrome window occlude only the covered area of the guest.
        return int(self.u.GetWindow(root, GW_HWNDPREV) or 0)

    def _raise_workspace_pair(self, root):
        """Lift the guest AND Launch as one normal-tier workspace.

        Putting Launch at HWND_TOP and later aligning an already-adjacent
        guest can leave both below Chrome. Instead, raise the guest first and
        insert Launch directly beneath that specific HWND. Neither call
        activates a window or makes a normal Launch permanently TOPMOST.
        """
        root_topmost = self._root_is_topmost(root)
        guest_topmost = bool(int(self.u.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE))
                             & WS_EX_TOPMOST)
        flags = SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE
        if root_topmost != guest_topmost:
            tier = HWND_TOPMOST if root_topmost else HWND_NOTOPMOST
            if not self.u.SetWindowPos(self.hwnd, tier, 0, 0, 0, 0, flags):
                return False
        tier = HWND_TOPMOST if root_topmost else HWND_TOP
        if not self.u.SetWindowPos(self.hwnd, tier, 0, 0, 0, 0, flags):
            return False
        if not self.u.SetWindowPos(root, self.hwnd, 0, 0, 0, 0, flags):
            return False
        # Native Qt history/dropdown Tool windows must stay above the editor,
        # including when recovery is triggered by foreground polling.
        for popup in self._popup_hwnds:
            if popup and popup != self.hwnd and self.u.IsWindow(popup):
                self.u.SetWindowPos(
                    popup, HWND_TOPMOST if root_topmost else HWND_TOP,
                    0, 0, 0, 0, flags)
        return self._window_above_launch(root) == self.hwnd

    def sync(self, *, panel_visible=True, popup_hwnds=(), qt_host_size=None):
        """Track geometry and position the guest immediately above Launch.

        Never hide solely because Chrome / another app takes focus. That made
        the visible portion of Launch's third column suddenly go blank. Also
        do not leave the guest permanently TOPMOST: it must stay behind any
        desktop window above Launch, including partly overlapping windows.
        """
        self._popup_hwnds = tuple(popup_hwnds or ())
        self._qt_host_size = qt_host_size
        # Undo prior region-based workaround if the same native window is
        # reused. Cutting holes made the desktop guest paint empty rectangles.
        self._popup_mask.clear()
        if not self.attached or not self.u.IsWindow(self.hwnd):
            return
        root = self._root_hwnd()
        if not root or not self.u.IsWindow(root):
            return
        rect = self._desktop_rect() if panel_visible else None
        if rect is None or bool(self.u.IsIconic(root)):
            self._last_sync_foreground = None
            self._popup_mask.clear()
            # Minimized/hidden Launch and a closed third column must still
            # hide the floating guest. Never change its parent or kill it.
            if self._visible:
                self.u.ShowWindow(self.hwnd, SW_HIDE)
                self._visible = False
            return

        foreground = int(self.u.GetForegroundWindow() or 0)
        newly_activated_guest = (foreground == self.hwnd and
                                 self._last_sync_foreground != self.hwnd)
        self._last_sync_foreground = foreground
        above = self._window_above_launch(root)
        # A genuine foreground transition is a second path to recover when
        # the delayed native mouse hook misses a click. The old condition only
        # checked whether guest was *immediately* above Launch; a third-party
        # window could still cover the entire pair without triggering repair.
        # Never change the background pair while Chrome has foreground.
        if (foreground == self.hwnd and
                (newly_activated_guest or
                 (above != self.hwnd and above not in self._popup_hwnds))):
            if self._raise_workspace_pair(root):
                above = self._window_above_launch(root)

        # A previous revision unconditionally set HWND_TOPMOST. When Launch is
        # a normal window (non-auto-dismiss mode), that made Obsidian float
        # above Chrome unless it was explicitly SW_HIDE'd. Restore the same
        # topmost tier as Launch before placing it in the desktop stack.
        root_topmost = self._root_is_topmost(root)
        guest_topmost = bool(int(self.u.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE))
                             & WS_EX_TOPMOST)
        if guest_topmost and not root_topmost:
            self.u.SetWindowPos(self.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE)
            above = self._window_above_launch(root)
        elif root_topmost and not guest_topmost:
            self.u.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE)
            above = self._window_above_launch(root)

        already_above = above == self.hwnd
        changed = rect != self._last_rect or not self._visible
        # Native Qt.Tool history popup HWNDs must remain above the guest.
        # SetWindowPos(hWndInsertAfter=popup) inserts the GUEST just BELOW the
        # popup. This preserves the whole Obsidian window and IME geometry;
        # SetWindowRgn is intentionally NOT used for popup priority.
        popup = next((p for p in self._popup_hwnds
                      if (p and p != self.hwnd and self.u.IsWindow(p)
                          and bool(int(self.u.GetWindowLongPtrW(p, GWL_EXSTYLE))
                                   & WS_EX_TOPMOST) == root_topmost)), 0)
        if not changed and already_above:
            return  # Launch / guest / popups already have their ideal stack.

        # 'insert after the window directly above Launch' positions Obsidian
        # in the precise gap ABOVE Launch and BELOW any unrelated app. If
        # Launch is itself the top of its Z-order tier, use the tier's top.
        after = (self.hwnd if already_above else (popup or above))
        if not already_above and not popup:
            # A normal Launch can be immediately below the TOPMOST tier.
            # Passing a TOPMOST neighbor as hWndInsertAfter would accidentally
            # promote this non-topmost guest, recreating the Chrome-overlap bug.
            # Keep the guest in Launch's own Z-order tier instead.
            if (not after or (not root_topmost and
                              (int(self.u.GetWindowLongPtrW(after, GWL_EXSTYLE))
                               & WS_EX_TOPMOST))):
                after = HWND_TOPMOST if root_topmost else HWND_TOP
        flags = SWP_NOACTIVATE
        # A native Windows caption needs SWP_FRAMECHANGED after changing style.
        # Keep the existing Chromium/Electron behavior untouched.
        if not self._visible and self.native_frame_on_attach:
            flags |= SWP_FRAMECHANGED
        if already_above:
            flags |= SWP_NOZORDER
        if not self._visible:
            flags |= SWP_SHOWWINDOW
        if self.u.SetWindowPos(self.hwnd, after, *rect, flags):
            self._last_rect = rect
            self._visible = True

    def raise_workspace_from_guest_click(self, x, y):
        """Raise the clicked guest/Launch pair while preserving guest IME.

        The native hook re-verifies the actual hit window; clicks on Chrome,
        Launch or a popup must not lift the guest. Diagnostic trace remains.
        """
        from guest_zorder_trace import write as guest_trace
        point = (x, y)
        guest_trace('overlay_enter', overlay=self, point=point)
        if not self.attached or not self._visible or not self.u.IsWindow(self.hwnd):
            guest_trace('overlay_skip', overlay=self, point=point,
                        reason='guest_not_attached_visible_or_valid')
            return False
        root = self._root_hwnd()
        if not root or not self.u.IsWindow(root) or bool(self.u.IsIconic(root)):
            guest_trace('overlay_skip', overlay=self, point=point,
                        reason='launch_missing_or_minimized')
            return False
        hit = int(self.u.WindowFromPoint(wintypes.POINT(int(x), int(y))) or 0)
        if not hit or not self.u.IsWindow(hit):
            guest_trace('overlay_skip', overlay=self, point=point,
                        reason='hit_invalid')
            return False
        if hit != self.hwnd and not self.u.IsChild(self.hwnd, hit):
            guest_trace('overlay_skip', overlay=self, point=point,
                        reason='hit_not_guest')
            return False  # Other app / popup was clicked.

        # Move guest first, then place Launch immediately beneath it.
        # _raise_workspace_pair applies SWP_NOACTIVATE to both windows.
        # A normal guest/root remains in the normal (non-TOPMOST) tier.
        raised = self._raise_workspace_pair(root)
        guest_trace('overlay_raise', overlay=self, point=point, success=int(raised))
        if not raised:
            return False

        # The pair helper already restored native popup priority. Avoid a
        # second raise in sync immediately after the same guest click.
        if int(self.u.GetForegroundWindow() or 0) == self.hwnd:
            self._last_sync_foreground = self.hwnd
        self.sync(popup_hwnds=self._popup_hwnds, qt_host_size=self._qt_host_size)
        guest_trace('overlay_synced', overlay=self, point=point,
                    popup_count=len(self._popup_hwnds))
        return True

    def resize(self, width, height):
        # Win32 physical host rectangle is authoritative (DPI-safe). Keep
        # the known native popup HWNDs so resizes preserve their Z-order.
        self.sync(popup_hwnds=self._popup_hwnds, qt_host_size=self._qt_host_size)

    def _restore_original(self, *, show_window):
        # Never leave a history-shaped hole in the detached desktop window.
        self._popup_mask.clear()
        if not self.u.IsWindow(self.hwnd):
            self.attached = False
            return
        self.u.ShowWindow(self.hwnd, SW_HIDE)
        self.u.SetWindowLongPtrW(self.hwnd, GWL_STYLE, self.original_style)
        self.u.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, self.original_exstyle)
        x, y, w, h = self.original_rect
        before_topmost = (self.original_exstyle & WS_EX_TOPMOST) != 0
        self.u.SetWindowPos(self.hwnd,
                            HWND_TOPMOST if before_topmost else HWND_NOTOPMOST,
                            x, y, w, h, SWP_NOACTIVATE | SWP_FRAMECHANGED)
        self.u.ShowWindow(self.hwnd,
                          SW_SHOWNOACTIVATE if show_window else SW_HIDE)
        self.attached = False
        self._visible = False
        _LIVE_OVERLAYS.discard(self)

    def detach(self, *, foreground=False, show_window=True):
        if not self.attached:
            return
        self._restore_original(show_window=show_window)
        if foreground and show_window and self.u.IsWindow(self.hwnd):
            self.u.SetForegroundWindow(self.hwnd)
