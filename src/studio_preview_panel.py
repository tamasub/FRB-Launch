"""Third Files column: native FRB Studio and external editor previews.

FRB Studio sessions keep unsaved edits when the pane is hidden. Sakura's
pre-existing desktop windows are never taken over: only a newly launched
editor HWND from a previously absent PID can be docked. × asks the editor
to close normally; explicit pop-out restores its desktop window.
"""
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QWidget, QLabel, QToolButton, QVBoxLayout,
                               QHBoxLayout, QSizePolicy, QStackedWidget, QMessageBox)
from browser_nav_icons import browser_navigation_icon
from launch_appearance import theme_family, theme_palette
from studio_preview_route import studio_start_command


class _NativeHost(QFrame):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setObjectName('studioNativeHost')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        window = self.owner._attached
        if window:
            window.resize(self.width(), self.height())
        if self.owner.status_label:
            self.owner.status_label.setGeometry(12, 12, max(100, self.width() - 24), 100)


class StudioPreviewPanel(QFrame):
    close_requested = Signal()
    popout_requested = Signal()
    sakura_close_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('filesStudioPreviewPanel')
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._theme = 'light'
        self._process = None
        self._attached = None
        self._target = None
        self._started = 0
        # Suspended Studio HWNDs are not destroyed. Keep their process and HWND
        # for a later reselect of the same file (including uncommitted edits).
        self._parked = {}
        self._options_widget = None
        # External editor pop-outs are separate from Studio's NativeShell
        # sessions. They are never killed by Preview's × button.
        self._external_key = None
        self._external_parked = {}
        self._external_pending = None
        # Sakura can open the next document in the SAME tabbed native window.
        # Track a handoff without unparenting the still-visible Sakura host.
        self._sakura_switch_from = None
        # HWND -> PID of Sakura windows positively identified as launched by
        # this Launch preview. Pre-existing user windows are NEVER owned.
        self._sakura_owned_windows = {}
        self._sakura_baseline_pids = None
        # Sakura window must have been independently verified as newly created
        # for this Launch request. Popen's return PID alone is insufficient.
        self._sakura_attached_pid = None
        self._sakura_transfer_consented = False
        self._sakura_close_wait_hwnd = None
        self._sakura_close_requested_at = 0.0
        self._sakura_close_timer = QTimer(self)
        self._sakura_close_timer.setInterval(350)
        self._sakura_close_timer.timeout.connect(self._poll_sakura_close)
        self._external_timer = QTimer(self)
        self._external_timer.setInterval(350)
        self._external_timer.timeout.connect(self._poll_external)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame(self)
        header.setObjectName('filesStudioPreviewHeader')
        bar = QHBoxLayout(header)
        bar.setContentsMargins(10, 4, 6, 4)
        self.title_label = QLabel('FRB Studio', header)
        self.title_label.setObjectName('filesStudioPreviewTitle')
        bar.addWidget(self.title_label, 1)
        self.close_button = QToolButton(header)
        self.close_button.setFixedSize(29, 29)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_button.setToolTip('第3列を閉じる')
        self.close_button.clicked.connect(self.close_requested.emit)
        self.popout_button = QToolButton(header)
        self.popout_button.setObjectName('filesEditorPopoutButton')
        self.popout_button.setFixedSize(29, 29)
        self.popout_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popout_button.setToolTip('サクラエディタを外に出す（終了しません）')
        self.popout_button.clicked.connect(self.pop_out_sakura)
        self.popout_button.hide()
        bar.addWidget(self.popout_button)
        bar.addWidget(self.close_button)
        layout.addWidget(header)
        self.content_stack = QStackedWidget(self)
        layout.addWidget(self.content_stack, 1)
        self.host = _NativeHost(self)
        self.content_stack.addWidget(self.host)
        self.status_label = QLabel('Studio 起動待ち…', self.host)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setGeometry(8, 8, 280, 80)
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._poll)
        self.apply_theme('light')

    def _sakura_trace(self, event, **details):
        # This is telemetry only. All errors are swallowed by the tracer.
        from sakura_window_trace import trace
        trace(event, **details)

    def _sakura_window_scan(self, stage, **details):
        from sakura_window_trace import trace_windows
        trace_windows(stage, **details)

    def open_document(self, target):
        """Display a real NativeShell session (never a copied HTML editor)."""
        self.content_stack.setCurrentWidget(self.host)
        if self._target == target and self._process and self._process.poll() is None:
            if self._attached:
                self._attached.resize(self.host.width(), self.host.height())
            return True
        self._park_current()
        if self._target is not None or self._external_key is not None:
            # The old HWND could not be detached safely. Leave it intact.
            return False
        old = self._parked.pop(target, None)
        if old is not None and old[0].poll() is None:
            self._process, hwnd = old
            self._target = target
            self._started = time.monotonic()
            self._show_target_title(target)
            if hwnd:
                try:
                    from studio_win32_host import AttachedStudioWindow
                    self._attached = AttachedStudioWindow(hwnd, int(self.host.winId()))
                    self._attached.resize(self.host.width(), self.host.height())
                    self.status_label.hide()
                    return True
                except (OSError, RuntimeError, ValueError):
                    # If the native HWND died, the live process may have been
                    # recreated; let the regular process poll look for it.
                    self._attached = None
            self.status_label.setText('Studioウィンドウへ再接続しています…')
            self.status_label.show()
            self._timer.start()
            return True
        command, working_directory = studio_start_command(target)
        try:
            self._process = subprocess.Popen(command, cwd=working_directory)
        except OSError as exc:
            self._process = None
            self._target = None
            self.status_label.setText('Studioの起動に失敗しました: ' + str(exc))
            self.status_label.show()
            return False
        self._target = target
        self._started = time.monotonic()
        self._show_target_title(target)
        self.status_label.setText('Studioを起動しています…\n編集・保存は既存Studioが担当します')
        self.status_label.show()
        self._timer.start()
        return True

    def open_external(self, target):
        """Open a NEW editor window, never adopt an existing Sakura session."""
        self.content_stack.setCurrentWidget(self.host)
        if target.app == 'sakura':
            getattr(self, '_sakura_trace', lambda *a, **k: None)(
                'OPEN_BEGIN', file=Path(target.path).name,
                pending=self._external_pending is not None,
                current_app=self._external_key[0] if self._external_key else '',
                attached_hwnd=getattr(self._attached, 'hwnd', None),
                parked=len(self._external_parked))
        if self._external_pending is not None:
            if target.app == 'sakura':
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'OPEN_SKIPPED', reason='previous_handoff_pending')
            return True  # Ignore extra double-clicks until native handoff settles.
        if self._external_key == target.key and self._attached:
            if target.app == 'sakura':
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'OPEN_REUSE_ATTACHED', hwnd=getattr(self._attached, 'hwnd', None))
            if self._attached:
                self._attached.resize(self.host.width(), self.host.height())
            return True
        # Opening the next tab in Sakura while the current HWND is hidden is
        # unsafe: Sakura may reuse precisely that HWND. Keep it attached and
        # visible until we know whether it switched tabs or opened a new HWND.
        if (target.app == 'sakura' and self._external_key is not None
                and self._external_key[0] == 'sakura' and self._attached is not None
                and self._attached.attached):
            getattr(self, '_sakura_trace', lambda *a, **k: None)(
                'OPEN_IN_EXISTING_DOCKED_TAB')
            return self._open_sakura_next(target)
        # A tabbed Sakura session is an editor window, not one document.
        # Do not release it merely because a different preview was selected.
        if self.sakura_attached():
            getattr(self, '_sakura_trace', lambda *a, **k: None)(
                'OPEN_SKIPPED', reason='sakura_already_docked')
            self._explain_sakura_switch_blocked()
            return False
        self._park_current()  # also parks a preceding external editor
        if self._target is not None or self._external_key is not None:
            if target.app == 'sakura':
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'OPEN_SKIPPED', reason='previous_editor_could_not_park',
                    current_app=self._external_key[0] if self._external_key else '')
            return False  # Failed to park: never overwrite an unsaved editor.
        self.title_label.setText(('Obsidian' if target.app == 'obsidian'
                                  else 'サクラエディタ') + ' — ' + Path(target.path).name)
        self.title_label.setToolTip(target.path)
        from studio_win32_host import AttachedStudioWindow
        previous = self._external_parked.pop(target.key, None)
        parked_key = target.key
        # In Sakura tab mode, several files can share one HWND. Reuse our own
        # parked Sakura session even when it was last used for another file.
        # Never take an unrelated existing Sakura desktop window.
        if previous is None and target.app == 'sakura':
            for key in reversed(tuple(self._external_parked)):
                if key[0] == 'sakura':
                    parked_key = key
                    previous = self._external_parked.pop(key)
                    break
        if previous:
            try:
                self._attached = AttachedStudioWindow(previous, int(self.host.winId()))
                self._attached.resize(self.host.width(), self.host.height())
                self._external_key = parked_key
                self._sync_popout_button()
                self.status_label.hide()
                if target.app == 'sakura' and parked_key != target.key:
                    return self._open_sakura_next(target)
                return True
            except (OSError, RuntimeError, ValueError):
                self._attached = None  # Native window was closed while parked.
        try:
            from external_win32_host import (snapshot_editor_windows,
                                             snapshot_editor_process_ids, editor_windows)
            if target.app == 'sakura':
                # A desktop Sakura can already have tabs and unsaved work.
                # Its own "external launch opens new window" option controls
                # whether a new window appears. Never prompt to borrow it.
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'DESKTOP_WINDOWS_LEFT_UNTOUCHED',
                    existing_count=len(editor_windows('sakura', include_hidden=False)))
            baseline = snapshot_editor_windows(target.app)
            # A Sakura file-open may be forwarded to an existing editor PID.
            # Never attach/close a HWND belonging to a pre-existing editor PID.
            self._sakura_baseline_pids = (snapshot_editor_process_ids('sakura')
                                         if target.app == 'sakura' else None)
            launched_pid = None
            if target.app == 'obsidian':
                import os
                from external_preview_route import obsidian_open_uri
                os.startfile(obsidian_open_uri(target.path, require_registered=True))
            elif target.app == 'sakura':
                from external_preview_route import external_start_command
                process = subprocess.Popen(external_start_command(target),
                                           cwd=str(Path(target.executable).parent))
                launched_pid = process.pid
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'SUBPROCESS_START', pid=launched_pid, file=Path(target.path).name)
            else:
                raise ValueError('未知の外部エディターです')
        except (OSError, ValueError, RuntimeError) as exc:
            if target.app == 'sakura':
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'OPEN_EXCEPTION', error_type=type(exc).__name__, error=str(exc))
            self.status_label.setText('エディターを開けませんでした: ' + str(exc))
            self.status_label.show()
            return False
        self._external_key = target.key
        self._external_pending = (target, baseline, launched_pid, time.monotonic())
        if target.app == 'sakura':
            getattr(self, '_sakura_trace', lambda *a, **k: None)(
                'POLL_WAIT_START', baseline_count=len(baseline),
                excluded_pids=sorted(self._sakura_baseline_pids or ()),
                launched_pid=launched_pid)
            self._sakura_trace_poll_logged = False
        self.status_label.setText(
            '外部エディターの新しいウィンドウを待っています…\n'
            '既存ウィンドウを奪わず、安全に収容できた場合だけ表示します')
        self.status_label.show()
        self._external_timer.start()
        return True

    def sakura_attached(self):
        return bool(self._external_key is not None and self._external_key[0] == 'sakura'
                    and self._attached is not None and self._attached.attached)

    def _sync_popout_button(self):
        button = getattr(self, 'popout_button', None)
        if button is not None:
            button.setVisible(self.sakura_attached())
        if getattr(self, 'close_button', None) is not None:
            self.close_button.setToolTip(
                'サクラエディタへ通常終了を要求（未保存時はエディタ側で確認）'
                if self.sakura_attached() else '第3列を隠す（編集状態を保持）')

    def _explain_sakura_switch_blocked(self):
        self.launcher.show_launch_notice(
            QMessageBox.Icon.Information, 'サクラエディタを収容中',
            'サクラエディタは第3列に収容中です。\n'
            '他のプレビューに切り替えるには、右上の「外に出す」か「×」を押してください。')

    def pop_out_sakura(self):
        """The ONLY interactive detach command for a docked Sakura session.

        Never close a tab or editor process. HWND + PID are checked because a
        recycled Win32 handle must not be operated on as the previous editor.
        """
        if not self.sakura_attached() or self._external_pending is not None:
            return False
        from external_win32_host import editor_window_pid
        attached = self._attached
        pid = getattr(self, '_sakura_attached_pid', None)
        if not pid or editor_window_pid(attached.hwnd) != pid:
            return False
        try:
            attached.detach(foreground=True, show_window=True)
        except (OSError, RuntimeError):
            return False
        self._sakura_close_timer.stop()
        self._sakura_close_wait_hwnd = None
        self._sakura_attached_pid = None
        self._sakura_transfer_consented = False
        self._sakura_owned_windows.pop(int(attached.hwnd), None)
        self._attached = None
        self._external_key = None
        self._external_pending = None
        self._sakura_switch_from = None
        self._sync_popout_button()
        self.popout_requested.emit()  # Parent hides the emptied pane.
        return True

    def _request_sakura_normal_close(self):
        """× means ordinary WM_CLOSE for this consented Sakura WINDOW.

        Keep its HWND embedded until Sakura has accepted the close. If Sakura
        asks about unsaved tabs and the user cancels, retain the entire window
        in Launch; neither detach nor delete any individual tabs.
        """
        if (not self.sakura_attached() or self._external_pending is not None
                or not self._sakura_transfer_consented):
            return False
        from external_win32_host import editor_window_pid
        from studio_win32_host import request_editor_window_close
        hwnd = int(self._attached.hwnd)
        pid = getattr(self, '_sakura_attached_pid', None)
        if not pid or editor_window_pid(hwnd) != pid:
            return False
        now = time.monotonic()
        if self._sakura_close_wait_hwnd == hwnd and now - self._sakura_close_requested_at < 1.0:
            return False  # Avoid double WM_CLOSE while save dialog is opening.
        request_editor_window_close(hwnd)
        self._sakura_close_wait_hwnd = hwnd
        self._sakura_close_requested_at = now
        self._sakura_close_timer.start()
        return False  # Async normal close; do not hide or undock yet.

    def _poll_sakura_close(self):
        hwnd = self._sakura_close_wait_hwnd
        if not hwnd:
            self._sakura_close_timer.stop()
            return
        from external_win32_host import editor_window_pid
        if editor_window_pid(hwnd) == self._sakura_attached_pid:
            return  # Save-confirmation remains open or close was cancelled.
        self._sakura_close_timer.stop()
        self._sakura_close_wait_hwnd = None
        self._sakura_owned_windows.pop(int(hwnd), None)
        self._sakura_attached_pid = None
        self._sakura_transfer_consented = False
        self._attached = None
        self._external_key = None
        self._sakura_switch_from = None
        self._sync_popout_button()
        self.sakura_close_completed.emit()

    def _open_sakura_next(self, target):
        """Request a second/third tab while Sakura remains a *visible* child.

        Sakura is allowed to use the same HWND for multiple documents. We
        first launch the document, then observe whether its caption changes or
        an additional HWND appears; reparent only AFTER detecting a new HWND.
        """
        if self._external_pending is not None:
            return False
        if (self._attached is not None and
                getattr(self, '_sakura_transfer_consented', False)
                and int(self._attached.hwnd) not in
                getattr(self, '_sakura_owned_windows', {})):
            # A previously running Sakura was explicitly BORROWED, not spawned.
            # Launching sakura.exe again can create another external window.
            # Never make that transition without a tested in-window open path.
            getattr(self, '_sakura_trace', lambda *a, **k: None)(
                'BORROWED_SAKURA_RELAUNCH_BLOCKED', requested=Path(target.path).name)
            self.title_label.setToolTip(
                f'{Path(target.path).name} はまだ開いていません。'
                '既存サクラエディタ側の「ファイル → 開く」で開いてください。')
            return False
        # A cancelled Sakura save prompt leaves the HWND alive. Never lock out
        # later tab navigation permanently because × was pressed once.
        if (getattr(self, '_sakura_close_wait_hwnd', None) is not None
                and time.monotonic() - getattr(self, '_sakura_close_requested_at', 0) < 1.5):
            return False
        try:
            from external_win32_host import snapshot_editor_windows, snapshot_editor_process_ids
            from external_preview_route import external_start_command
            baseline = snapshot_editor_windows('sakura')
            self._sakura_baseline_pids = snapshot_editor_process_ids('sakura')
            proc = subprocess.Popen(external_start_command(target),
                                    cwd=str(Path(target.executable).parent))
        except (OSError, ValueError, RuntimeError) as exc:
            self.status_label.setText('次のテキストを開けませんでした: ' + str(exc))
            self.status_label.show()
            return False
        self._sakura_switch_from = (self._external_key, self.title_label.text())
        self._external_pending = (target, baseline, proc.pid, time.monotonic())
        self.title_label.setText('サクラエディタ — ' + Path(target.path).name)
        self.title_label.setToolTip(target.path)
        self._external_timer.start()
        return True

    def external_embedded_active(self):
        """Native-child focus is inside Launch for BOTH Sakura and Obsidian.

        Qt may report ApplicationInactive when the external process gets focus.
        Prevent the Launch auto-dismiss hook from undocking the editor while
        the user is typing. Studio's original behavior is unchanged.
        """
        return bool(self.isVisible() and self._external_key is not None
                    and self._attached is not None and self._attached.attached)

    def focus_external_after_native_click(self, x, y):
        """Give the clicked editor native input focus for Sakura AND Obsidian.

        Both are cross-process Win32 children. The click must actually land on
        the attached HWND; the shared Win32 helper rejects other applications,
        toolbar/list clicks and delayed events, so it never transfers typing
        from Files List merely because a preview is visible.
        """
        if (self._external_key is None
                or self._external_key[0] not in ('obsidian', 'sakura')
                or not self.external_embedded_active()):
            return False
        from studio_win32_host import focus_embedded_editor_from_click
        return focus_embedded_editor_from_click(
            self._attached.hwnd, int(self.host.winId()), x, y)

    def focus_obsidian_after_native_click(self, x, y):
        """Backwards-compatible name for the previous Obsidian-only hook."""
        return self.focus_external_after_native_click(x, y)

    def obsidian_embedded_active(self):
        """Compatibility alias for existing Launch callers/tests."""
        return self.external_embedded_active()

    def prepare_to_hide(self):
        """Park Electron *outside* the hidden Qt widget before Preview ×.

        Hiding a Qt parent while Chromium remains attached as a native child
        can leave the renderer in an inconsistent state. Keep the document
        session alive, detached and invisible, ready to reattach on reopen.
        """
        if self._external_key is not None and self._external_key[0] == 'obsidian':
            self._park_external()

    def _close_owned_sakura(self, hwnd):
        """WM_CLOSE only for a HWND created in a new Sakura PID by Launch.

        Never close an existing desktop Sakura instance, even when opening a
        file from Launch reused that window/tab. A PID check prevents a stale
        HWND from being closed after Windows reuses the handle.
        """
        hwnd = int(hwnd)
        owned = getattr(self, '_sakura_owned_windows', {})
        expected_pid = owned.pop(hwnd, None)
        if not expected_pid:
            return True  # Not ours: restore/detach only, never close.
        from external_win32_host import editor_window_pid
        if editor_window_pid(hwnd) != expected_pid:
            return True  # Closed/reused since docking: do not touch it.
        from studio_win32_host import request_editor_window_close
        request_editor_window_close(hwnd)  # WM_CLOSE only; editor handles save.
        return True

    def close_external_editors(self):
        """Handle explicit ×. Sakura stays docked while WM_CLOSE is pending.

        Sakura itself decides whether unsaved tabs can close. Never detach it
        or hide the Launch pane before the native window actually closes.
        Other external editors retain the earlier safe close path.
        """
        if self._external_pending is not None:
            # An editor has been launched but the HWND has not yet been
            # identified. Hiding now would leave an unmanaged application
            # window to appear later. Let detection finish before closing.
            self.status_label.setText(
                '外部エディターの起動・切替中です。表示が確定してから×で閉じてください。')
            self.status_label.show()
            return False
        if getattr(self, 'sakura_attached', lambda: False)():
            return self._request_sakura_normal_close()
        self._external_timer.stop()
        self._sakura_switch_from = None
        windows = []
        if self._external_key is not None:
            attached = self._attached
            if attached is not None:
                try:
                    attached.detach(foreground=False, show_window=True)
                    windows.append((attached.hwnd, self._external_key[0]))
                    self._attached = None
                except (OSError, RuntimeError):
                    # Don't attempt to kill an editor still attached to Qt.
                    return False
            self._external_key = None
        if self._external_parked:
            from studio_win32_host import restore_parked_studio_window
            for key, hwnd in tuple(self._external_parked.items()):
                try:
                    restore_parked_studio_window(hwnd)
                    windows.append((hwnd, key[0]))
                except (OSError, RuntimeError, ValueError):
                    # Preserve failed HWNDs for a future recovery attempt.
                    return False
            self._external_parked.clear()
        if windows:
            from studio_win32_host import request_editor_window_close
            for hwnd, app in set(windows):
                try:
                    if app != 'sakura':
                        request_editor_window_close(hwnd)
                    # Stale Sakura entries from older sessions are restored,
                    # never closed without an explicit currently docked ×.
                except (OSError, RuntimeError, ValueError):
                    return False
        return True

    def external_embedding_pending(self):
        """Keep Launch visible during brief external-app startup handoff."""
        return self._external_pending is not None

    def _poll_external(self):
        pending = self._external_pending
        if pending is None:
            self._external_timer.stop()
            return
        target, baseline, launched_pid, started = pending
        if target.app == 'sakura' and not getattr(self, '_sakura_trace_poll_logged', False):
            getattr(self, '_sakura_trace', lambda *a, **k: None)(
                'POLL_FIRST_TICK', elapsed_ms=int((time.monotonic() - started)*1000),
                launched_pid=launched_pid)
            self._sakura_trace_poll_logged = True
        switching_sakura = target.app == 'sakura' and self._sakura_switch_from is not None
        try:
            from external_win32_host import find_new_editor_window
            excluded = (getattr(self, '_sakura_baseline_pids', None)
                        if target.app == 'sakura' else None)
            if excluded is None:
                hwnd = find_new_editor_window(target, baseline, launched_pid)
            else:
                hwnd = find_new_editor_window(target, baseline, launched_pid, excluded)
            if switching_sakura and not hwnd and self._attached is not None:
                # Tab-mode reuse: the embedded HWND stays the same and only
                # its active document/caption changes. Do NOT SetParent again.
                from external_win32_host import editor_window_title
                caption = editor_window_title(self._attached.hwnd)
                if Path(target.path).name.casefold() in caption.casefold():
                    self._external_key = target.key
                    self._external_pending = None
                    self._sakura_switch_from = None
                    self._external_timer.stop()
                    return
            # Do not adopt an existing user's Sakura HWND even if Sakura
            # routes this file-open into that existing tab group. A separate
            # editor window is required for Launch's third column.
            if hwnd:
                if target.app == 'sakura':
                    getattr(self, '_sakura_trace', lambda *a, **k: None)(
                        'POLL_NEW_HWND', hwnd=hwnd, excluded_pids=sorted(excluded or ()))
                # Refuse pre-existing editor PIDs even if a new HWND or title
                # appeared after the launch request. Never steal a desktop tab.
                sakura_pid = None
                if target.app == 'sakura' and excluded is not None:
                    from external_win32_host import editor_window_pid
                    sakura_pid = editor_window_pid(hwnd)
                    if not sakura_pid or sakura_pid in excluded:
                        raise RuntimeError('既存のサクラエディタはLaunchへ取り込みません')
                from studio_win32_host import AttachedStudioWindow
                if switching_sakura:
                    # Sakura unexpectedly opened another HWND. Keep the original
                    # embedded session as-is; never detach it automatically.
                    self._external_pending = None
                    self._external_timer.stop()
                    self._sakura_switch_from = None
                    self.status_label.setText(
                        '別のサクラエディタウィンドウが開きました。\n'
                        '第3列のウィンドウはそのまま維持しています。')
                    self.status_label.show()
                    return
                self._attached = AttachedStudioWindow(hwnd, int(self.host.winId()))
                self._attached.resize(self.host.width(), self.host.height())
                if target.app == 'sakura' and sakura_pid:
                    self._sakura_owned_windows[int(hwnd)] = sakura_pid
                    self._sakura_attached_pid = sakura_pid
                    self._sakura_transfer_consented = True
                self._external_key = target.key
                self._sync_popout_button()
                self.status_label.hide()
                self._external_pending = None
                self._sakura_switch_from = None
                self._external_timer.stop()
                return
        except (OSError, RuntimeError, ValueError) as exc:
            if target.app == 'sakura':
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'POLL_EXCEPTION', error_type=type(exc).__name__, error=str(exc))
            self._external_timer.stop()
            self._external_pending = None
            if switching_sakura and self._sakura_switch_from:
                self._external_key, previous_title = self._sakura_switch_from
                self.title_label.setText(previous_title)
            self._sakura_switch_from = None
            self.status_label.setText('第3列への収容に失敗しました。外側のアプリで編集できます。\n' + str(exc))
            self.status_label.show()
            return
        # A failed obsidian:// URI may only show a Vault error dialog.
        # Do not block the Preview close action for 30 seconds in that case.
        timeout = 6 if switching_sakura else (12 if target.app == 'obsidian' else 25)
        if time.monotonic() - started > timeout:
            if target.app == 'sakura':
                getattr(self, '_sakura_trace', lambda *a, **k: None)(
                    'POLL_TIMEOUT', elapsed_seconds=round(time.monotonic()-started, 2))
                getattr(self, '_sakura_window_scan', lambda *a, **k: None)('poll_timeout')
            self._external_timer.stop()
            self._external_pending = None
            if switching_sakura and self._sakura_switch_from:
                self._external_key, previous_title = self._sakura_switch_from
                self.title_label.setText(previous_title)
                self.status_label.setText(
                    '新しいサクラエディタの表示先を確認できませんでした。\n'
                    '安全のため、現在の編集画面を維持します。')
            else:
                if target.app == 'sakura':
                    self.status_label.setText(
                        '新しいサクラエディタのウィンドウを確認できませんでした。\n'
                        '既存の編集画面は取り込んでいません。\n'
                        'サクラの「共通設定 → タブバー → '
                        '外部から起動するときは新しいウィンドウで開く」を確認してください。')
                else:
                    self.status_label.setText(
                        '新しい編集ウィンドウを特定できませんでした。\n'
                        '既存アプリの画面は安全のため収容していません。\n'
                        'Obsidianの場合はVault登録を確認してください。')
            self._sakura_switch_from = None
            self.status_label.show()

    def _park_external(self):
        if self._external_key is None:
            return
        is_sakura = self._external_key[0] == 'sakura'
        if is_sakura:
            # Strict Sakura contract: no implicit WM_CLOSE, detach or parking.
            # The explicit pop-out and × commands own those transitions.
            return False
        self._external_timer.stop()
        self._external_pending = None
        self._sakura_switch_from = None
        attached = self._attached
        if attached is not None:
            try:
                attached.detach(foreground=False, show_window=False)
                self._external_parked[self._external_key] = attached.hwnd
            except (OSError, RuntimeError):
                return False
            self._attached = None
        self._external_key = None
        getattr(self, '_sync_popout_button', lambda: None)()
        return True

    def _show_target_title(self, target):
        name = 'Launch メニュー設定' if len(target) > 3 else Path(target[0]).name
        self.title_label.setText('FRB Studio — ' + name)
        self.title_label.setToolTip(target[0])

    def open_options(self, launch_home, state_dir, studio_root):
        """Reuse the existing Qt WebEngine + Node save bridge as a child pane."""
        if self.sakura_attached():
            self._explain_sakura_switch_blocked()
            return False
        if self._options_widget is None:
            from option_settings_window import OptionSettingsWindow
            options = OptionSettingsWindow(launch_home, state_dir,
                                           studio_root=studio_root, parent=self,
                                           theme=self._theme)
            # OptionSettingsWindow is the real dialog implementation. Host it
            # as a plain Qt child; its WebEngine/Node save code is unchanged.
            options.setWindowFlags(Qt.WindowType.Widget)
            options.setMinimumSize(280, 250)
            self.content_stack.addWidget(options)
            self._options_widget = options
        self.content_stack.setCurrentWidget(self._options_widget)
        self.title_label.setText('FRB Launch — オプション設定')
        self.title_label.setToolTip('')
        return True

    def _poll(self):
        if not self._process or not self._target:
            self._timer.stop()
            return
        if self._process.poll() is not None:
            self._timer.stop()
            self.status_label.setText('Studioが終了しました。×で第3列を閉じてください。')
            self.status_label.show()
            self._process = None
            return
        try:
            from studio_win32_host import find_studio_main_window, AttachedStudioWindow
            hwnd = find_studio_main_window(self._process.pid)
            if hwnd:
                # Ensure Qt creates a native HWND before docking WinForms.
                self._attached = AttachedStudioWindow(hwnd, int(self.host.winId()))
                self._attached.resize(self.host.width(), self.host.height())
                self.status_label.hide()
                self._timer.stop()
                return
        except (OSError, RuntimeError, ValueError) as exc:
            self._timer.stop()
            self.status_label.setText('第3列への収容に失敗しました。\n別ウィンドウのStudioを使用してください。\n' + str(exc))
            self.status_label.show()
            return
        if time.monotonic() - self._started > 35:
            self._timer.stop()
            self.status_label.setText('Studioの表示を確認できません。\n別ウィンドウで開いている場合はそちらを使用してください。')
            self.status_label.show()

    def _park_current(self):
        """Put the previous NativeShell on an invisible desktop, not a popup."""
        self._timer.stop()
        # This path is called when the user switches to/from C# Studio as well
        # as between external editors. Preserve the other app before reuse.
        if getattr(self, 'sakura_attached', lambda: False)():
            return False  # No automatic Sakura pop-out on document switch.
        if getattr(self, '_external_key', None) is not None:
            self._park_external()
            if self._external_key is not None:
                return
        attached = self._attached
        process = self._process
        target = self._target
        self._attached = self._process = self._target = None
        if not target or not process or process.poll() is not None:
            return
        hwnd = None
        if attached is not None:
            hwnd = attached.hwnd
            try:
                attached.detach(foreground=False, show_window=False)
            except (OSError, RuntimeError):
                # If detachment fails, never terminate the unsaved process.
                # It remains a child of the host and can be restored on exit.
                self._attached, self._process, self._target = attached, process, target
                return
        self._parked[target] = (process, hwnd)

    def undock(self):
        """Restore all live Studio windows only when Launch itself exits."""
        self._timer.stop()
        self._external_timer.stop()
        self._sakura_close_timer.stop()
        self._sakura_close_wait_hwnd = None
        self._external_pending = None
        active = self._attached
        self._attached = None
        if active is not None:
            try:
                active.detach(foreground=False)
            except (OSError, RuntimeError):
                pass
        # Parked windows are already detached but hidden, so make them visible
        # before the Launch process goes away. The user can save them normally.
        if self._parked:
            try:
                from studio_win32_host import restore_parked_studio_window
                for process, hwnd in self._parked.values():
                    if hwnd and process.poll() is None:
                        restore_parked_studio_window(hwnd)
            except (OSError, RuntimeError, ValueError):
                pass
        self._parked.clear()
        if self._external_parked:
            from studio_win32_host import restore_parked_studio_window
            for hwnd in self._external_parked.values():
                try:
                    restore_parked_studio_window(hwnd)
                except (OSError, RuntimeError, ValueError):
                    pass
            self._external_parked.clear()
        self._external_key = None
        self._sakura_owned_windows.clear()
        self._sakura_baseline_pids = None
        self._sakura_attached_pid = None
        self._sakura_transfer_consented = False
        self._sync_popout_button()
        self._process = None
        self._target = None
        if self._options_widget is not None:
            self._options_widget.close()
            self._options_widget = None
        self.title_label.setText('FRB Studio')
        self.title_label.setToolTip('')
        self.status_label.setText('')
        self.status_label.show()

    def apply_theme(self, theme):
        self._theme = theme
        c = theme_palette(theme)
        self.close_button.setIcon(browser_navigation_icon('close', theme_family(theme)))
        self.popout_button.setIcon(browser_navigation_icon('external', theme_family(theme)))
        if self._options_widget is not None:
            self._options_widget.set_theme(theme)
        self.setStyleSheet(f'''
            QFrame#filesStudioPreviewPanel {{background:{c['panel']};border:0;}}
            QFrame#filesStudioPreviewHeader {{background:{c['panel_header']};border-bottom:1px solid {c['panel_border']};}}
            QLabel#filesStudioPreviewTitle {{color:{c['text']};font-size:13px;font-weight:600;}}
            QToolButton {{background:transparent;border:0;border-radius:5px;}}
            QToolButton:hover {{background:{c['hover']};}}
            QFrame#studioNativeHost {{background:{c['panel']};border:0;}}
            QLabel {{color:{c['text']};}}
        ''')
