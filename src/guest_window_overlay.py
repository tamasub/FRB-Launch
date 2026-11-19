"""External editor top-level overlays, without cross-process SetParent.

Electron guests use Obsidian's existing popup-style adapter. Sakura is a
classic Win32/GDI editor and must keep its original native styles to repaint
its text, tabs, toolbars and status bar correctly when switching documents.
"""
from obsidian_ime_overlay import ObsidianImeOverlay


class GuestWindowOverlay(ObsidianImeOverlay):
    """Non-parented Chromium/Electron window guest."""


class SakuraGuestOverlay(GuestWindowOverlay):
    """Non-parented Sakura guest retaining its original Win32 appearance.

    Do not use WS_POPUP or WS_EX_TOOLWINDOW on a classic GDI editor merely
    because that works for Obsidian/VS Code. This class never calls SetParent.
    """
    # WS_CAPTION/WS_THICKFRAME are never modified. Sending FRAMECHANGED for
    # an unchanged native window can cause Sakura to rebuild its client panes.
    native_frame_on_attach = False
    preserve_native_styles = True

    def _overlay_window_style(self):
        return self.original_style

    def refresh_document(self):
        """Invalidate the document and *child* panes after a tab handoff.

        Sakura can dispatch its next-file request into the same HWND. A
        top-level overlay does not receive Qt's internal update scheduling;
        request native GDI repaint once after the editor has processed the
        file-open event. Do not change its parent, focus or document data.
        """
        from studio_win32_host import RDW_INVALIDATE, RDW_ALLCHILDREN
        RDW_ERASE = 0x0004
        if not self.attached or not self.u.IsWindow(self.hwnd):
            return False
        return bool(self.u.RedrawWindow(
            self.hwnd, 0, 0, RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_ERASE))

    def _restore_original(self, *, show_window):
        """Release a native GDI editor without the Electron hide/style cycle.

        Sakura keeps its Win32 styles on attach. Reapplying identical styles
        with SetWindowLongPtr and SWP_FRAMECHANGED, particularly while hidden,
        can leave its tab body and toolbars blank after a desktop pop-out.
        Normal top-level movement generates WM_SIZE naturally; invalidate the
        native child tree once the editor is shown again. Never SetParent,
        WM_CLOSE, or touch document contents.
        """
        from obsidian_ime_overlay import (
            _LIVE_OVERLAYS, HWND_TOPMOST, HWND_NOTOPMOST, WS_EX_TOPMOST,
        )
        from studio_win32_host import (
            GWL_STYLE, GWL_EXSTYLE, SW_HIDE, SW_SHOWNOACTIVATE,
            SWP_NOACTIVATE, SWP_FRAMECHANGED,
        )

        self._popup_mask.clear()
        if not self.u.IsWindow(self.hwnd):
            self.attached = False
            self._visible = False
            _LIVE_OVERLAYS.discard(self)
            return

        # Sakura never had its style altered by the overlay. Avoid needless
        # WM_STYLECHANGING/CHANGED, and correct only genuine deviations.
        style_drifted = (int(self.u.GetWindowLongPtrW(self.hwnd, GWL_STYLE))
                         != self.original_style)
        if style_drifted:
            self.u.SetWindowLongPtrW(self.hwnd, GWL_STYLE, self.original_style)
        current_exstyle = int(self.u.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE))
        exstyle_drifted = bool((current_exstyle ^ self.original_exstyle)
                               & ~WS_EX_TOPMOST)
        if exstyle_drifted:
            self.u.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE,
                                     self.original_exstyle)

        if not show_window:
            # Hidden parking must not flash the editor at its desktop size.
            self.u.ShowWindow(self.hwnd, SW_HIDE)
        x, y, w, h = self.original_rect
        tier = (HWND_TOPMOST if self.original_exstyle & WS_EX_TOPMOST
                else HWND_NOTOPMOST)
        # Move/resize first: Windows delivers the native WM_SIZE needed for
        # Sakura's tab/status/toolbar layout. Only use FRAMECHANGED when a
        # genuine external style deviation had to be repaired.
        flags = (SWP_NOACTIVATE | SWP_FRAMECHANGED
                 if style_drifted or exstyle_drifted else SWP_NOACTIVATE)
        if not self.u.SetWindowPos(self.hwnd, tier, x, y, w, h, flags):
            raise OSError('サクラエディタの元の位置を復元できません')
        if show_window:
            self.u.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.refresh_native_frame()

        self.attached = False
        self._visible = False
        self._last_rect = None
        _LIVE_OVERLAYS.discard(self)

    def refresh_native_frame(self):
        """Invalidate desktop Sakura's non-client area and all GDI children.

        RedrawWindow without RDW_UPDATENOW avoids synchronously waiting on
        another process's UI thread. This never takes focus or alters style.
        """
        from studio_win32_host import RDW_INVALIDATE, RDW_ALLCHILDREN, RDW_FRAME
        redraw = getattr(self.u, 'RedrawWindow', None)
        if redraw is None or not self.u.IsWindow(self.hwnd):
            return False
        RDW_ERASE = 0x0004
        return bool(redraw(self.hwnd, 0, 0,
                           RDW_INVALIDATE | RDW_ALLCHILDREN |
                           RDW_FRAME | RDW_ERASE))
