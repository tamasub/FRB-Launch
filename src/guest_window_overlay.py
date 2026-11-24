"""External editor top-level overlays, without cross-process SetParent.

Electron guests use Obsidian's existing popup-style adapter. Sakura is a
classic Win32/GDI editor and must keep its original native styles to repaint
its text, tabs, toolbars and status bar correctly when switching documents.
"""
import time

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

    @staticmethod
    def _sakura_park_mode():
        """Minimize parked Sakura by default; explicit 'hide' is a rollback.

        The native top-level Sakura window remains alive with its unsaved
        document contents intact.  Only Sakura is affected by this setting.
        """
        import os
        configured = os.environ.get('FRB_SAKURA_PARK_MODE', '').strip().lower()
        return 'hide' if configured == 'hide' else 'minimize'

    def __init__(self, hwnd, host_hwnd, *, user32=None):
        # An intentionally minimized parked Sakura must be returned to its
        # NORMAL window placement *before* the base overlay captures its
        # original rectangle. A minimized HWND can report (-32000, -32000).
        if user32 is None:
            from studio_win32_host import _user32
            user32 = _user32()
        # The parent configures this signature only *after* __init__ starts;
        # the early iconic probe also needs 64-bit safe HWND arguments.
        if hasattr(user32, 'IsIconic'):
            from ctypes import wintypes
            user32.IsIconic.argtypes = [wintypes.HWND]
            user32.IsIconic.restype = wintypes.BOOL
        if (user32.IsWindow(int(hwnd)) and
                bool(getattr(user32, 'IsIconic', lambda h: False)(int(hwnd)))):
            from third_column_window_state import prepare_native_redock
            if not prepare_native_redock(int(hwnd), user32=user32):
                raise OSError('最小化したサクラエディタを復元できません')
        super().__init__(hwnd, host_hwnd, user32=user32)

    def _overlay_window_style(self):
        return self.original_style

    def _trace_sakura_sync(self, event, *, force=False, **details):
        """Low-volume, opt-out trace; no captions, paths or document contents."""
        now = time.monotonic()
        if not force and now - getattr(self, '_sakura_last_trace_at', 0.0) < 3.0:
            return
        self._sakura_last_trace_at = now
        # _last_rect is only the planned/accepted SetWindowPos rectangle,
        # not proof of the native HWND's actual desktop coordinates.
        if event in ('SYNC_HEARTBEAT', 'SYNC_UNEXPECTED_GUEST_STATE'):
            details.update(self._sakura_native_geometry())
            # A HWND may be WS_VISIBLE and correctly positioned, yet hidden
            # *behind* the Launch root. Native z-order/point hit is the only
            # reliable way to distinguish that from a genuine GDI blank.
            details.update(self._sakura_native_stacking())
        from sakura_window_trace import trace
        trace(event, hwnd=int(self.hwnd), attached=bool(self.attached),
              tracked_visible=bool(self._visible), **details)

    def _sakura_native_geometry(self):
        """Read-only Win32 geometry; no repaint, focus or style manipulation."""
        import ctypes
        from ctypes import wintypes
        read_rect = getattr(self.u, 'GetWindowRect', None)
        def rect_of(hwnd):
            if not read_rect or not hwnd or not self.u.IsWindow(hwnd):
                return None
            rect = wintypes.RECT()
            try:
                if not read_rect(hwnd, ctypes.byref(rect)):
                    return None
            except (OSError, ValueError, RuntimeError, TypeError):
                return None
            return [int(rect.left), int(rect.top),
                    int(rect.right - rect.left), int(rect.bottom - rect.top)]
        root = self._root_hwnd()
        native = rect_of(self.hwnd)
        planned = self._desktop_rect()
        return dict(native_guest_rect=native,
                    native_root_rect=rect_of(root),
                    planned_host_rect=list(planned) if planned else None)

    def _sakura_native_stacking(self):
        """Read-only Z-order and hit-test for a physically blank third column.

        WS_VISIBLE is *not* proof the guest is on screen: a different native
        window (including Launch) can cover it. Do not repair/reorder here.
        The probe samples only the center of the third-column host, so a
        foreground third-party window is distinguishable from a broken pair.
        """
        from ctypes import wintypes
        u = self.u
        root = int(self._root_hwnd() or 0)
        guest = int(self.hwnd)
        result = {
            'native_host_hwnd': int(self.host_hwnd),
            'native_root_hwnd': root,
            'native_guest_hwnd': guest,
        }
        get_window = getattr(u, 'GetWindow', None)
        get_foreground = getattr(u, 'GetForegroundWindow', None)
        if get_foreground:
            try:
                result['native_foreground_hwnd'] = int(get_foreground() or 0)
            except (OSError, ValueError, RuntimeError, TypeError):
                result['native_foreground_hwnd'] = None
        if get_window and root and u.IsWindow(root) and u.IsWindow(guest):
            try:
                # GW_HWNDPREV: prior (higher) window in the desktop stack.
                above_root = int(get_window(root, 3) or 0)
                above_guest = int(get_window(guest, 3) or 0)
                result['native_above_root_hwnd'] = above_root
                result['native_above_guest_hwnd'] = above_guest
                result['native_guest_immediately_above_root'] = above_root == guest

                def appears_above(target, candidate):
                    seen = {target}
                    cursor = target
                    for _ in range(128):
                        cursor = int(get_window(cursor, 3) or 0)
                        if not cursor or cursor in seen:
                            break
                        if cursor == candidate:
                            return True
                        seen.add(cursor)
                    return False

                result['native_guest_above_root'] = appears_above(root, guest)
                result['native_root_above_guest'] = appears_above(guest, root)
            except (OSError, ValueError, RuntimeError, TypeError):
                result['native_zorder_error'] = True

        hit_test = getattr(u, 'WindowFromPoint', None)
        get_ancestor = getattr(u, 'GetAncestor', None)
        rect = self._desktop_rect()
        if hit_test and rect:
            x, y, width, height = rect
            point = (x + width // 2, y + height // 2)
            try:
                hit = int(hit_test(wintypes.POINT(*point)) or 0)
                hit_root = int(get_ancestor(hit, 2) or 0) if hit and get_ancestor else hit
                result.update(native_probe_point=list(point),
                              native_hit_hwnd=hit,
                              native_hit_root_hwnd=hit_root,
                              native_guest_is_hit_root=(hit_root == guest),
                              native_launch_is_hit_root=(hit_root == root))
            except (OSError, ValueError, RuntimeError, TypeError):
                result['native_hit_test_error'] = True
        return result

    def sync(self, *, panel_visible=True, popup_hwnds=(), qt_host_size=None):
        """Keep native Sakura alive through transient Qt reflow/move states.

        The Electron policy is intentionally unchanged. A Qt visibility/host
        geometry blip while its Launch root remains visible is NOT a request
        to hide Sakura. A genuinely hidden or minimized Launch still uses the
        normal hide branch in the parent implementation.
        """
        # ShowWindow(SW_HIDE) in _restore_original is intentional parking.
        # Native Win32 messages can reenter Qt/our sync path before that
        # cross-process hide/move operation returns.  Never interpret that
        # temporary hidden state as a recoverable crash and SWP_SHOWWINDOW
        # the retired editor (which can leave overlapping GDI windows).
        if getattr(self, '_sakura_detaching', False):
            self._trace_sakura_sync('SYNC_SKIPPED_DURING_DETACH', force=True)
            return
        if not self.attached or not self.u.IsWindow(self.hwnd):
            return super().sync(panel_visible=panel_visible,
                                popup_hwnds=popup_hwnds,
                                qt_host_size=qt_host_size)
        # Keep popup-priority inputs current even when a transient Qt reflow
        # asks us to skip moving the guest for this single timer tick.
        self._popup_hwnds = tuple(popup_hwnds or ())
        self._qt_host_size = qt_host_size
        root = self._root_hwnd()
        root_valid = bool(root and self.u.IsWindow(root))
        is_iconic = getattr(self.u, 'IsIconic', lambda hwnd: False)
        is_visible = getattr(self.u, 'IsWindowVisible', None)
        root_minimized = bool(is_iconic(root)) if root_valid else False
        root_shown = bool(is_visible(root)) if (root_valid and is_visible) else True
        # A hidden Launch root is an intentional hide, even if Qt has not yet
        # emitted its child visibility update.
        if root_valid and not root_shown:
            panel_visible = False
        geometry = self._desktop_rect() if panel_visible else None
        # Only ignore *temporary* Qt child/host visibility or geometry loss.
        # When the actual Launch root is hidden/minimized, normal SW_HIDE
        # remains necessary. Explicit pane close/popout uses detach instead.
        if (root_valid and root_shown and not root_minimized
                and (not panel_visible or geometry is None)):
            self._trace_sakura_sync('SYNC_TRANSIENT_HOLD',
                                    panel_visible=bool(panel_visible),
                                    rect_available=geometry is not None)
            return

        guest_minimized = bool(is_iconic(self.hwnd))
        guest_visible = bool(is_visible(self.hwnd)) if is_visible else bool(self._visible)
        usable_host = (root_valid and root_shown and not root_minimized
                       and panel_visible and geometry is not None)
        if usable_host and (guest_minimized or (self._visible and not guest_visible)):
            self._trace_sakura_sync('SYNC_UNEXPECTED_GUEST_STATE', force=True,
                                    guest_minimized=guest_minimized,
                                    guest_visible=guest_visible,
                                    root_minimized=root_minimized)
            # This is a docked, Launch-verified editor. Its own native HWND
            # can become iconic/hidden without an explicit detach. Never
            # spawn a second Sakura; restore this same HWND and realign it.
            if guest_minimized:
                from studio_win32_host import SW_RESTORE
                self.u.ShowWindow(self.hwnd, SW_RESTORE)
            self._visible = False  # force parent sync to re-show the same HWND

        before_rect = self._last_rect
        before_visible = self._visible
        if before_visible and (root_minimized or not root_shown):
            self._trace_sakura_sync('SYNC_ROOT_HIDING', force=True,
                                    root_minimized=root_minimized,
                                    root_shown=root_shown)
        super().sync(panel_visible=panel_visible,
                     popup_hwnds=popup_hwnds,
                     qt_host_size=qt_host_size)
        if before_rect != self._last_rect or before_visible != self._visible:
            self._trace_sakura_sync('SYNC_UPDATED', force=True,
                                    panel_visible=bool(panel_visible),
                                    guest_minimized=guest_minimized,
                                    guest_visible=guest_visible,
                                    root_minimized=root_minimized,
                                    root_shown=root_shown,
                                    rect_changed=before_rect != self._last_rect,
                                    rect=self._last_rect)
        else:
            self._trace_sakura_sync('SYNC_HEARTBEAT',
                                    panel_visible=bool(panel_visible),
                                    guest_minimized=guest_minimized,
                                    guest_visible=guest_visible,
                                    root_minimized=root_minimized,
                                    root_shown=root_shown)

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
        """Guard the complete native hide/move/show lifecycle against reentry."""
        self._sakura_detaching = True
        visible = getattr(self.u, 'IsWindowVisible', None)
        self._trace_sakura_sync(
            'DETACH_BEGIN', force=True, requested_visible=bool(show_window),
            actual_visible=bool(visible(self.hwnd)) if visible else None)
        try:
            self._restore_sakura_original(show_window=show_window)
        except Exception as exc:
            self._trace_sakura_sync('DETACH_FAILED', force=True,
                                    error_type=type(exc).__name__)
            raise
        else:
            self._trace_sakura_sync(
                'DETACH_DONE', force=True, requested_visible=bool(show_window),
                actual_visible=bool(visible(self.hwnd)) if visible else None)
        finally:
            self._sakura_detaching = False

    def _restore_sakura_original(self, *, show_window):
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

        # For hidden parking, do NOT first call ShowWindow(SW_HIDE).  The old
        # two-step sequence hid the HWND and then sent a second native
        # move/size/Z-order request to the already hidden GDI window.  On the
        # reported Windows 11 desktop this leaves its old visual surface on
        # screen even though IsWindowVisible is false.  Request the original
        # geometry and hide in ONE SetWindowPos transaction instead.
        x, y, w, h = self.original_rect
        tier = (HWND_TOPMOST if self.original_exstyle & WS_EX_TOPMOST
                else HWND_NOTOPMOST)
        # Move/resize first: Windows delivers the native WM_SIZE needed for
        # Sakura's tab/status/toolbar layout. Only use FRAMECHANGED when a
        # genuine external style deviation had to be repaired.
        flags = (SWP_NOACTIVATE | SWP_FRAMECHANGED
                 if style_drifted or exstyle_drifted else SWP_NOACTIVATE)
        minimize_park = not show_window and self._sakura_park_mode() == 'minimize'
        if not show_window and not minimize_park:
            # This HWND is intentionally retired while the next document is
            # docked. On some Windows GDI/DWM combinations the old client
            # surface remains in Launch's backing area even though
            # IsWindowVisible has already become false. Drop retained pixels
            # as part of one hide-and-move request; never show or destroy the
            # retired editor (unsaved text must survive).
            SWP_HIDEWINDOW = 0x0080
            SWP_NOCOPYBITS = 0x0100
            flags |= SWP_HIDEWINDOW | SWP_NOCOPYBITS
        if not self.u.SetWindowPos(self.hwnd, tier, x, y, w, h, flags):
            raise OSError('サクラエディタの元の位置を復元できません')
        if show_window:
            self.u.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.refresh_native_frame()
        elif minimize_park:
            # Standard parking: use the native minimize lifecycle rather than
            # hiding a live GDI top-level HWND (which left dead visual surfaces
            # on the observed Windows 11 setup).
            # Windows taskbar may show minimized editors. HWNDs/document data
            # are preserved; failure keeps this overlay attached for recovery.
            from third_column_window_state import park_native_window
            minimized = park_native_window(self.hwnd, user32=self.u)
            self._trace_sakura_sync('PARKED_MINIMIZE_TRIAL_RESULT', force=True,
                                    strategy='minimize', actual_minimized=minimized,
                                    actual_visible=bool(self.u.IsWindowVisible(self.hwnd)))
            if not minimized:
                raise OSError('サクラの最小化退避に失敗しました')
        else:
            # Some foreign window procedures can override a hide request.
            # Keep the old ShowWindow path as an exceptional safety fallback,
            # NEVER an unconditional second hide/geometry operation.
            query_visible = getattr(self.u, 'IsWindowVisible', None)
            fallback_used = False
            if query_visible is not None and bool(query_visible(self.hwnd)):
                fallback_used = True
                self.u.ShowWindow(self.hwnd, SW_HIDE)
            actual_hidden = (not bool(query_visible(self.hwnd))
                             if query_visible is not None else None)
            self._trace_sakura_sync('PARKED_ATOMIC_HIDE_RESULT', force=True,
                                    hide_via_setwindowpos=True,
                                    hide_fallback_used=fallback_used,
                                    actual_hidden=actual_hidden)
            # A genuinely still-visible retired window must NOT be silently
            # registered as hidden.  Retain ownership for recovery instead.
            if actual_hidden is False:
                raise OSError('サクラエディタを非表示にできませんでした')
            # The external native editor paints above Qt, not into Qt's
            # backing store. Invalidate the Launch root when withdrawing the
            # old GDI surface so exposed header/status strips are painted.
            # No immediate synchronous paint or DWM blocking call here.
            from studio_win32_host import RDW_INVALIDATE, RDW_ALLCHILDREN
            RDW_ERASE = 0x0004
            root = self._root_hwnd()
            redraw = getattr(self.u, 'RedrawWindow', None)
            repaired = None
            if root and self.u.IsWindow(root) and redraw is not None:
                try:
                    repaired = bool(redraw(root, 0, 0,
                        RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_ERASE))
                except (OSError, ValueError, RuntimeError, TypeError):
                    repaired = False
            self._trace_sakura_sync('PARKED_SURFACE_INVALIDATED', force=True,
                                    root_hwnd=root,
                                    root_redraw_requested=repaired,
                                    discard_old_client_bits=True)

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
