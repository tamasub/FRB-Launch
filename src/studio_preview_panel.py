"""Third Files column: native FRB Studio and external editor previews.

FRB Studio sessions keep unsaved edits when the pane is hidden. Sakura's
existing desktop windows are never auto-borrowed: only independently verified
new Sakura HWNDs can be docked. Obsidian instead borrows its MAIN vault window
through a CLI-verified document and unique native caption (no pop-outs).
Closing the Obsidian pane returns its main window to the desktop, never WM_CLOSE.
"""
import subprocess
import os
import time
import threading
import uuid
import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QEventLoop
from PySide6.QtWidgets import (QFrame, QWidget, QLabel, QToolButton, QVBoxLayout,
                               QHBoxLayout, QSizePolicy, QStackedWidget, QMessageBox)
from browser_nav_icons import browser_navigation_icon
from launch_appearance import theme_family, theme_palette
from studio_preview_route import studio_start_command


class _NativeHost(QFrame):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        # Only this host needs an HWND for SetParent.  Qt otherwise turns its
        # entire ancestor chain into native child windows on first preview,
        # which can leave an unpainted strip beside Launch's rounded frame.
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
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
    _launch_switch_completed = Signal(object, str)
    _studio_popout_ack = Signal(str)
    _studio_dock_completed = Signal(int, str)
    _launch_exit_completed = Signal(str)
    _obsidian_cli_completed = Signal(str, object, str, int, str)
    _obsidian_main_probe_completed = Signal(str, object, str)

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
        self._launch_pipe_token = None
        self._launch_switch_pending = None
        self._launch_switch_completed.connect(self._on_launch_switch_completed)
        self._studio_popout_ack.connect(self._finish_studio_popout)
        self._studio_dock_completed.connect(self._on_studio_dock_completed)
        self._studio_dock_pending = False
        self._studio_popout_pending = False
        # Suspended Studio HWNDs are not destroyed. Keep their process and HWND
        # for a later reselect of the same file (including uncommitted edits).
        self._parked = {}
        self._options_widget = None
        # External editor pop-outs are separate from Studio's NativeShell
        # sessions. They are never killed by Preview's × button.
        self._external_key = None
        self._external_parked = {}
        # Never borrow a parked Obsidian HWND for a DIFFERENT registered vault.
        # Record the authenticated vault at parking time, not via a later path lookup.
        self._obsidian_parked_vaults = {}
        self._external_pending = None
        # A positively identified vault MAIN window may be borrowed and docked.
        # Probe through CLI first; never mistake a pop-out for the main HWND.
        self._obsidian_cli_token = None
        self._obsidian_cli_vault = None
        self._obsidian_cli_hwnd = None
        self._obsidian_cli_ready = False
        self._obsidian_cli_busy = None
        self._obsidian_cli_queued = None
        self._obsidian_cli_completed.connect(self._on_obsidian_cli_completed)
        self._obsidian_main_probe_completed.connect(self._on_obsidian_main_probe_completed)
        self._obsidian_main_probe_token = None
        self._obsidian_main_probe_busy = False
        self._obsidian_main_probe_attempts = 0
        self._obsidian_main_open_issued = False
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
        self._embedded_health_timer = QTimer(self)
        self._embedded_health_timer.setInterval(950)
        self._embedded_health_timer.timeout.connect(self._check_embedded_editor_health)
        self._embedded_health_timer.start()
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
        self.popout_button.setToolTip('第3列のエディターを外に出す（終了しません）')
        self.popout_button.clicked.connect(self.pop_out_selected)
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

    def _switch_launch_document(self, target):
        """Switch the existing Launch-owned NativeShell, never fork per JSON."""
        if self._launch_switch_pending is not None:
            return True  # A second double click must not queue an unsafe handoff.
        if not self._launch_pipe_token or not self._process or self._process.poll() is not None:
            return False
        self._launch_switch_pending = target
        self.status_label.setText('Studioの表示ファイルを切り替えています…')
        # Never block Qt: Studio can present an unsaved confirmation in WebView2.
        token = self._launch_pipe_token

        def submit():
            result = 'ERROR: Studioへの接続に失敗しました'
            address = r'\\.\pipe\frb_studio_launch_' + token
            for attempt in range(80):
                try:
                    with open(address, 'r+b', buffering=0) as channel:
                        # A Launch-maintenance JSON requires more than its path:
                        # send the validated CLI context with each reuse request.
                        # A plain document carries an empty argument list, which
                        # clears the previous launch ViewDef/focus context.
                        request = {'path': str(target[0]),
                                   'args': list(target[3]) if len(target) > 3 else []}
                        channel.write((json.dumps(request, ensure_ascii=False,
                                                  separators=(',', ':')) + '\n').encode('utf-8'))
                        # The C# pipe replies only after the unsaved guard resolves.
                        reply = channel.readline()
                        result = reply.decode('utf-8', errors='replace').strip() if reply else 'ERROR: Studio接続が切断されました'
                    break
                except OSError as exc:
                    if self._process is None or self._process.poll() is not None:
                        result = 'ERROR: Studioプロセスが終了しました'
                        break
                    if attempt == 79:
                        result = 'ERROR: Studio切替パイプに接続できません: ' + str(exc)
                    else:
                        time.sleep(0.15)
            self._launch_switch_completed.emit(target, result)

        threading.Thread(target=submit, name='FRBStudioLaunchSwitch', daemon=True).start()
        return True

    def _notify_studio_docked(self):
        """Reveal a Launch-only transparent NativeShell after SetParent succeeds.

        The session-specific pipe is already used for document switches and
        pop-out.  Never block the Qt thread waiting for Studio/WebView2.
        Older Studio builds have no DOCKED command and stay visibly docked.
        """
        if (self._studio_dock_pending or not self._launch_pipe_token or
                self._process is None or self._process.poll() is not None or
                self._attached is None or not self._attached.attached):
            return
        pid = self._process.pid
        token = self._launch_pipe_token
        self._studio_dock_pending = True
        self._sync_popout_button()

        def acknowledge():
            result = 'ERROR: Studioの収容確認に失敗しました'
            address = r'\\.\pipe\frb_studio_launch_' + token
            for attempt in range(60):
                try:
                    with open(address, 'r+b', buffering=0) as channel:
                        channel.write(b'@FRB_LAUNCH_DOCKED@\n')
                        reply = channel.readline()
                        result = reply.decode('utf-8', errors='replace').strip() if reply else 'ERROR: Studioから応答がありません'
                    break
                except OSError as exc:
                    result = 'ERROR: ' + str(exc)
                    if self._process is None or self._process.poll() is not None:
                        break
                    if attempt != 59:
                        time.sleep(0.15)
            self._studio_dock_completed.emit(pid, result)

        threading.Thread(target=acknowledge, name='FRBStudioDockReveal', daemon=True).start()

    def _on_studio_dock_completed(self, pid, result):
        if self._process is None or self._process.pid != pid:
            return  # Stale response after release/restart: never reveal it.
        self._studio_dock_pending = False
        if self._attached is not None and self._attached.attached:
            if result == 'OK':
                self.status_label.hide()
            else:
                # Earlier Studio builds do not know the dock protocol, but
                # their initially visible window was still docked normally.
                self.status_label.setText('Studioの静かな収容確認に失敗しました。\n' + result)
                self.status_label.show()
        self._sync_popout_button()

    def _on_launch_switch_completed(self, target, result):
        if self._launch_switch_pending != target:
            return
        self._launch_switch_pending = None
        if result == 'OK':
            self._target = target
            self._show_target_title(target)
            self.status_label.hide()
        elif result == 'CANCEL':
            # Keep current C# document, HWND and save target as they were.
            self.status_label.hide()
        else:
            self.status_label.setText('Studioのファイル切替に失敗しました。\n' + result)
            self.status_label.show()

    def open_document(self, target):
        """One Launch-owned NativeShell process; switch its real save grant."""
        self.content_stack.setCurrentWidget(self.host)
        if self._process and self._process.poll() is None and self._target is not None:
            if self._external_key is not None:
                self._park_external()
                if self._external_key is not None:
                    return False
            # Even a reselect of the same file is a deliberate reload: the
            # page may have been reset, and no in-memory view may remain.
            if self._attached:
                self._attached.resize(self.host.width(), self.host.height())
            return self._switch_launch_document(target)

        self._park_current()
        if self._target is not None or self._external_key is not None:
            return False  # Keep unsaved foreign editors untouched.
        old_target = target
        old = self._parked.pop(target, None)
        if old is None:
            # Reuse an earlier Launch-owned session even for a DIFFERENT JSON.
            for parked_target, parked in tuple(self._parked.items()):
                if parked[0].poll() is None:
                    old_target = parked_target
                    old = self._parked.pop(parked_target)
                    break
        if old is not None and old[0].poll() is None:
            self._process, hwnd = old
            self._target = old_target
            self._started = time.monotonic()
            self._show_target_title(old_target)
            if hwnd:
                try:
                    from studio_win32_host import AttachedStudioWindow
                    self._attached = AttachedStudioWindow(hwnd, int(self.host.winId()))
                    self._attached.resize(self.host.width(), self.host.height())
                    self._notify_studio_docked()
                    self.status_label.hide()
                    return self._switch_launch_document(target)
                except (OSError, RuntimeError, ValueError):
                    self._attached = None
            self.status_label.setText('Studioウィンドウへ再接続しています…')
            self.status_label.show()
            self._timer.start()
            # The existing process is still the sole session. Switch through
            # its private pipe instead of starting a second NativeShell.
            return self._switch_launch_document(target)

        command, working_directory = studio_start_command(target)
        self._launch_pipe_token = uuid.uuid4().hex
        self._studio_dock_pending = False
        command += ['--launch-preview', '--launch-preview-pipe=' + self._launch_pipe_token,
                    '--launch-preview-owner-pid=' + str(os.getpid())]
        try:
            self._process = subprocess.Popen(command, cwd=working_directory)
        except OSError as exc:
            self._process = None
            self._target = None
            self._launch_pipe_token = None
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

    def _obsidian_switch_unavailable(self, reason=''):
        """Keep the existing Obsidian main window; never spawn a pop-out.

        The caller treats True as 'the existing pane remains usable', not as
        confirmation that the requested document switched. The warning is
        deliberately visible until a successful switch or explicit close.
        """
        self.status_label.setText(
            'Obsidian本体のウィンドウを保持しています。\n'
            'ファイル切替は実行できませんでした。新しい窓は作成しません。\n'
            + (reason or 'Obsidian CLIの設定・対象Vaultを確認してください。'))
        self.status_label.show()
        return True

    def _release_obsidian_for_vault_change(self):
        """Undo only Launch's embedding of the current MAIN window.

        A different vault has its own MAIN HWND. The old window must remain a
        working desktop Obsidian with all notes/unsaved changes intact. Never
        send WM_CLOSE, quit Obsidian or transplant a window between vaults.
        """
        attached = self._attached
        if (self._external_key is None or self._external_key[0] != 'obsidian'
                or attached is None or not attached.attached):
            return False
        try:
            attached.detach(foreground=False, show_window=True)
            if attached.attached:
                return False
            # AttachedStudioWindow.detach() does not raise for every Win32
            # failure. A residual Qt-parented HWND MUST NOT be abandoned.
            native = getattr(attached, 'u', None)
            if (native is not None and native.IsWindow(int(attached.hwnd))
                    and int(native.GetParent(int(attached.hwnd)) or 0) ==
                    int(attached.host_hwnd)):
                return False
        except (OSError, RuntimeError, ValueError):
            return False
        from obsidian_dock_trace import trace
        trace('VAULT_CHANGE_RELEASE', hwnd=int(attached.hwnd))
        self._attached = None
        self._external_key = None
        self._external_timer.stop()
        self._external_pending = None
        self._obsidian_main_probe_token = None
        self._reset_obsidian_cli()
        self._sync_popout_button()
        return True

    def open_external(self, target):
        """Dock the vault's MAIN Obsidian window; do not create pop-outs.

        The CLI verifies both file and main-window caption before any HWND is
        adopted. Repeated opens use the tagged main Markdown leaf. Failure
        never creates a fallback pop-out. Sakura behavior is independent.
        """
        self.content_stack.setCurrentWidget(self.host)
        if target.app == 'obsidian':
            # Validate BEFORE releasing any existing editor. A missing CLI or
            # unregistered vault must never make the old note disappear.
            from obsidian_dock_bridge import registered_note, find_cli
            selected_note = registered_note(target.path)
            if selected_note is None or not find_cli():
                return self._obsidian_switch_unavailable(
                    '対象の保管庫が未登録、またはObsidian CLIが利用できません。')
        if target.app == 'sakura':
            getattr(self, '_sakura_trace', lambda *a, **k: None)(
                'OPEN_BEGIN', file=Path(target.path).name,
                pending=self._external_pending is not None,
                current_app=self._external_key[0] if self._external_key else '',
                attached_hwnd=getattr(self._attached, 'hwnd', None),
                parked=len(self._external_parked))
        if (target.app == 'obsidian' and self._external_pending is not None
                and self._external_pending[0].app == 'obsidian'):
            # A second click while the main-window handshake is pending.
            self._obsidian_cli_queued = target
            return True
        if (target.app == 'obsidian' and self._external_key is not None
                and self._external_key[0] == 'obsidian'):
            attached = self._attached
            if attached is None or not attached.attached:
                return self._obsidian_switch_unavailable('第3列の収容状態を確認できません。')
            if self._obsidian_cli_busy in ('bind', 'switch'):
                self._obsidian_cli_queued = target  # latest click wins after bind/switch
                return True
            if self._obsidian_cli_vault != selected_note[0]:
                from obsidian_dock_trace import fingerprint, trace
                trace('VAULT_CHANGE_REQUEST',
                      old_vault_hash=fingerprint(self._obsidian_cli_vault or ''),
                      new_vault_hash=fingerprint(selected_note[0]))
                # Another vault is a DIFFERENT native MAIN window. Restore the
                # previous vault to the desktop first; a new CLI+HWND handshake
                # below must positively identify the requested vault.
                if not self._release_obsidian_for_vault_change():
                    return self._obsidian_switch_unavailable(
                        '旧保管庫のウィンドウを安全に復元できませんでした。')
            else:
                # Same vault: stay in one editing leaf, no new native window.
                if target.key == self._external_key:
                    attached.resize(self.host.width(), self.host.height())
                    return True
                if self._obsidian_cli_ready and self._switch_obsidian_inside(target):
                    return True
                return self._obsidian_switch_unavailable()
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
        previous = None
        parked_key = target.key
        if target.app == 'obsidian':
            # The file path is NOT the native window identity. Reuse only an
            # HWND previously verified for the selected registered vault.
            # Never pick the last parked Obsidian window across vaults.
            for key in reversed(tuple(self._external_parked)):
                if (key[0] == 'obsidian' and
                        self._obsidian_parked_vaults.get(key) == selected_note[0]):
                    parked_key = key
                    previous = self._external_parked.pop(key)
                    self._obsidian_parked_vaults.pop(key, None)
                    break
        else:
            previous = self._external_parked.pop(target.key, None)
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
                if target.app == 'obsidian':
                    from external_preview_route import ExternalPreviewTarget
                    # Show the actual parked note until CLI confirms a switch;
                    # do not label the old document as the requested new one.
                    self.title_label.setText('Obsidian — ' + Path(parked_key[1]).name)
                    self.title_label.setToolTip(parked_key[1])
                    # The parked HWND still displays its OLD document. Bind
                    # that original leaf first, then switch if requested.
                    original = (target if parked_key == target.key else
                                ExternalPreviewTarget('obsidian', parked_key[1]))
                    bound = self._begin_obsidian_cli_bind(original, int(previous))
                    if parked_key != target.key:
                        if bound:
                            self._obsidian_cli_queued = target
                        else:
                            return self._obsidian_switch_unavailable()
                return True
            except (OSError, RuntimeError, ValueError) as exc:
                self._attached = None  # Never create a second window on failure.
                if target.app == 'obsidian':
                    self._external_parked[parked_key] = previous
                    self._obsidian_parked_vaults[parked_key] = selected_note[0]
                    self._external_key = None
                    return self._obsidian_switch_unavailable(
                        '退避済みウィンドウへ再接続できません: ' + str(exc))
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
                from obsidian_dock_bridge import registered_note, find_cli
                # A CLI handshake is mandatory: it positively identifies the
                # main window instead of stealing any visible Obsidian HWND.
                if registered_note(target.path) is None or not find_cli():
                    raise ValueError('Obsidian CLIを有効にし、対象Vaultを登録してください。')
                from urllib.parse import quote
                # Ask Obsidian to open/focus the registered VAULT only. The
                # CLI then opens the note in a verified MAIN root leaf, never
                # the last active pop-out tab. No paneType/window URI exists.
                vault_id, _note = registered_note(target.path)
                os.startfile('obsidian://open?vault=' + quote(vault_id, safe=''))
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
        if target.app == 'obsidian':
            from obsidian_dock_trace import trace, trace_windows
            trace('DOCK_REQUEST', existing_window_count=len(baseline),
                  note_registered=True, cli_found=True)
            trace_windows('dock_request_before_probe')
            self._obsidian_main_probe_token = uuid.uuid4().hex
            self._obsidian_main_probe_busy = False
            self._obsidian_main_probe_attempts = 0
            self._obsidian_main_open_issued = False
            self.status_label.setText(
                'Obsidian本体のウィンドウを確認中…\n'
                'CLIで対象ノートと本体を確認してから第3列へ収容します')
        else:
            self.status_label.setText(
                '外部エディターの新しいウィンドウを待っています…\n'
                '既存ウィンドウを奪わず、安全に収容できた場合だけ表示します')
        self.status_label.show()
        self._external_timer.start()
        if target.app == 'obsidian':
            self._probe_obsidian_main_window(self._obsidian_main_probe_token)
        return True

    def _probe_obsidian_main_window(self, token):
        """Ask Obsidian which MAIN window now contains the requested note.

        This runs off the Qt UI thread and does not use SetParent or scan
        unrelated HWNDs until the vault explicitly verifies the note.
        """
        pending = self._external_pending
        if (pending is None or pending[0].app != 'obsidian'
                or token != self._obsidian_main_probe_token
                or self._obsidian_main_probe_busy or self._obsidian_main_probe_attempts >= 12):
            return
        target = pending[0]
        self._obsidian_main_probe_busy = True
        self._obsidian_main_probe_attempts += 1
        # One opening request per handoff, then read-only verification.
        # If main DOM was still loading, allow a later retry to reissue open.
        request_open = not self._obsidian_main_open_issued
        if request_open:
            self._obsidian_main_open_issued = True
        from obsidian_dock_trace import trace
        trace('PROBE_START', attempt=self._obsidian_main_probe_attempts,
              request_open=request_open)

        def worker():
            from obsidian_dock_bridge import (registered_note, find_cli,
                                              main_open_code, main_verify_code, cli_eval)
            note = registered_note(target.path)
            cli = find_cli()
            if note is None or not cli:
                result = 'FRB_NO_CLI'
            else:
                if request_open:
                    opened = cli_eval(note[0], main_open_code(note[1]),
                                      executable=cli, stage='main_open')
                    trace('MAIN_OPEN_RESULT', result_code=opened.partition(':')[0])
                    if opened in ('FRB_NOT_FOUND', 'FRB_MAIN_NOT_READY'):
                        result = ('FRB_MAIN_OPEN_NOT_READY' if opened == 'FRB_MAIN_NOT_READY'
                                  else opened)
                        self._obsidian_main_probe_completed.emit(token, target, result)
                        return
                # The first CLI command may execute the openFile() but lose its
                # async reply. Never infer success from the reply: verify state
                # in a completely separate read-only CLI call instead.
                result = cli_eval(note[0], main_verify_code(note[1]),
                                  executable=cli, stage='main_verify')
            self._obsidian_main_probe_completed.emit(token, target, result)

        threading.Thread(target=worker, name='FRBObsidianMainProbe', daemon=True).start()

    def _on_obsidian_main_probe_completed(self, token, target, result):
        """Reparent ONLY the unique native HWND named by the verified main DOM."""
        pending = self._external_pending
        if (pending is None or pending[0] != target or pending[0].app != 'obsidian'
                or self._obsidian_main_probe_token != token):
            return
        self._obsidian_main_probe_busy = False
        from obsidian_dock_trace import trace
        trace('PROBE_RESPONSE', attempt=self._obsidian_main_probe_attempts,
              result_code=str(result).partition(':')[0])
        if result == 'FRB_MAIN_OPEN_NOT_READY':
            self._obsidian_main_open_issued = False
        if result.startswith('FRB_MAIN_TITLE:'):
            from urllib.parse import unquote
            from external_win32_host import editor_windows
            from obsidian_dock_bridge import main_window_matches_caption
            caption = unquote(result.partition(':')[2])
            windows = editor_windows('obsidian', include_hidden=True)
            from obsidian_dock_trace import fingerprint, trace_windows
            trace('CAPTION_MATCH', expected_hash=fingerprint(caption),
                  expected_length=len(caption), candidate_count=len(windows),
                  candidates=[{'hwnd': int(h), 'pid': int(p),
                               'caption_hash': fingerprint(t), 'caption_length': len(t)}
                              for h,p,t in windows[:35]])
            # Full native enumeration is comparatively expensive: collect it
            # at the first and last probe only; lightweight candidates log
            # continues on every response without slowing the Qt event loop.
            if self._obsidian_main_probe_attempts in (1, 12):
                trace_windows('caption_match', expected_caption=caption)
            hwnd = main_window_matches_caption(caption, windows)
            trace('HWND_SELECTION', success=bool(hwnd), hwnd=int(hwnd or 0),
                  exact_matches=sum(str(t).strip().casefold()==caption.strip().casefold()
                                    for h,p,t in windows))
            if hwnd:
                from studio_win32_host import AttachedStudioWindow
                try:
                    trace('SETPARENT_BEGIN', hwnd=int(hwnd))
                    attached = AttachedStudioWindow(hwnd, int(self.host.winId()))
                    attached.resize(self.host.width(), self.host.height())
                    trace('SETPARENT_SUCCESS', hwnd=int(hwnd))
                except (OSError, RuntimeError, ValueError) as exc:
                    trace('SETPARENT_FAILED', hwnd=int(hwnd), error_type=type(exc).__name__,
                          winerror=getattr(exc, 'winerror', None))
                    self._fail_obsidian_main_dock('本体の収容に失敗しました: ' + str(exc))
                    return
                self._attached = attached
                self._external_key = target.key
                self._external_pending = None
                self._external_timer.stop()
                self._obsidian_main_probe_token = None
                from embedded_obsidian_presentation import prefer_light_native_frame
                prefer_light_native_frame(hwnd)
                # Tagged leaf in the MAIN DOM also closes its left sidebar.
                trace('MAIN_ATTACHED', hwnd=int(hwnd))
                if not self._begin_obsidian_cli_bind(target, hwnd):
                    self._attached = None
                    self._external_key = None
                    attached.detach(foreground=False, show_window=True)
                    self._fail_obsidian_main_dock('Obsidian CLIへ再接続できません')
                    return
                self.status_label.hide()
                self._sync_popout_button()
                owner = getattr(self, 'launcher', None)
                if owner is not None and owner.isVisible():
                    QTimer.singleShot(0, owner.activateWindow)
                return
        # The URI handoff can take time. Recheck, but never emit another URI.
        if self._obsidian_main_probe_attempts < 12 and time.monotonic() - pending[3] < 14:
            QTimer.singleShot(450, lambda t=token: self._probe_obsidian_main_window(t))
        else:
            self._fail_obsidian_main_dock(
                'Obsidian本体のウィンドウを一意に確認できませんでした。'
                'Vault/CLI設定と、同名の別ウィンドウがないか確認してください。')

    def _fail_obsidian_main_dock(self, reason):
        """Leave the real Obsidian window untouched and visible on failure."""
        from obsidian_dock_trace import trace
        trace('MAIN_DOCK_FAILED', attempts=self._obsidian_main_probe_attempts,
              reason_kind='not_uniquely_verified')
        self._external_timer.stop()
        self._external_pending = None
        self._external_key = None
        self._obsidian_main_probe_token = None
        self._obsidian_main_probe_busy = False
        self._obsidian_cli_queued = None
        self.status_label.setText(reason + '\nObsidian本体はデスクトップ側で使用できます。')
        self.status_label.show()

    def _reset_obsidian_cli(self):
        self._obsidian_cli_token = None
        self._obsidian_cli_vault = None
        self._obsidian_cli_hwnd = None
        self._obsidian_cli_ready = False
        self._obsidian_cli_busy = None
        self._obsidian_cli_queued = None

    def _begin_obsidian_cli_bind(self, target, hwnd):
        """Bind only a main-window HWND verified by CLI and Win32 caption.

        CLI is required for main-window docking; vault settings are untouched.
        """
        from obsidian_dock_bridge import registered_note, find_cli, bind_main_code
        note = registered_note(target.path)
        cli = find_cli()
        # Preserve clicks that arrived while the first main HWND was pending.
        # Finish the bind before switching to the most recent note.
        queued = self._obsidian_cli_queued
        self._reset_obsidian_cli()
        self._obsidian_cli_queued = queued
        if note is None or not cli:
            return False
        self._obsidian_cli_vault = note[0]
        self._obsidian_cli_token = uuid.uuid4().hex
        self._obsidian_cli_hwnd = int(hwnd)
        from obsidian_dock_trace import trace
        trace('BIND_START', hwnd=int(hwnd))
        self._run_obsidian_cli('bind', target, note[0],
                               bind_main_code(note[1], self._obsidian_cli_token), cli)
        return True

    def _switch_obsidian_inside(self, target):
        from obsidian_dock_bridge import registered_note, find_cli, switch_main_code
        note = registered_note(target.path)
        cli = find_cli()
        if (note is None or cli is None or note[0] != self._obsidian_cli_vault
                or not self._obsidian_cli_token):
            return False
        from obsidian_dock_trace import trace
        trace('SWITCH_START', hwnd=int(self._obsidian_cli_hwnd or 0))
        self._run_obsidian_cli('switch', target, note[0],
                               switch_main_code(note[1], self._obsidian_cli_token), cli)
        return True

    def _run_obsidian_cli(self, kind, target, vault, script, cli):
        """Never make a blocking CLI call on the Qt GUI thread."""
        self._obsidian_cli_busy = kind
        hwnd = self._obsidian_cli_hwnd
        token = self._obsidian_cli_token

        def worker():
            from obsidian_dock_bridge import cli_eval
            result = cli_eval(vault, script, executable=cli, stage=kind)
            self._obsidian_cli_completed.emit(kind, target, result, hwnd, token)

        threading.Thread(target=worker, name='FRBObsidianDock', daemon=True).start()

    def _on_obsidian_cli_completed(self, kind, target, result, hwnd, token):
        attached = self._attached
        if (self._obsidian_cli_token != token or self._obsidian_cli_hwnd != hwnd or attached is None
                or int(attached.hwnd) != hwnd or not attached.attached
                or self._external_key is None or self._external_key[0] != 'obsidian'):
            return  # An earlier worker must never mutate a replaced preview.
        if self._obsidian_cli_busy != kind:
            return
        self._obsidian_cli_busy = None
        self._obsidian_cli_ready = (result == ('FRB_BOUND' if kind == 'bind'
                                             else 'FRB_SWITCHED'))
        from obsidian_dock_trace import trace
        trace('CLI_HANDSHAKE_COMPLETED', kind=kind, hwnd=int(hwnd or 0),
              result_code=str(result).partition(':')[0], accepted=self._obsidian_cli_ready)
        if kind == 'bind' and not self._obsidian_cli_ready:
            self._obsidian_cli_queued = None
            self._obsidian_switch_unavailable(
                'Obsidian本体をCLIで特定できません (' + result + ')。')
            return
        if kind == 'switch':
            if result == 'FRB_SWITCHED':
                self._external_key = target.key
                self.title_label.setText('Obsidian — ' + Path(target.path).name)
                self.title_label.setToolTip(target.path)
                self.status_label.hide()
            else:
                # A CLI timeout can mean the async open completed despite a
                # missing reply. Do not automatically create a second popup:
                # that would risk a duplicate window/tab and confuse editing.
                self.status_label.setText(
                    'Obsidianの切替完了を確認できませんでした。\n'
                    '現在の表示内容はLaunch側では確認できません。別のファイルを再度選ぶか、'
                    '必要なら第3列を閉じて開き直してください。')
                self.status_label.show()
                self._obsidian_cli_queued = None
                self._obsidian_cli_ready = False
                return
        queued = self._obsidian_cli_queued
        self._obsidian_cli_queued = None
        if queued is not None and queued.key != self._external_key:
            # Only an authenticated main leaf may receive this request.
            # Never open another native window as a fallback.
            self.open_external(queued)

    def sakura_attached(self):
        return bool(self._external_key is not None and self._external_key[0] == 'sakura'
                    and self._attached is not None and self._attached.attached)

    def _sync_popout_button(self):
        button = getattr(self, 'popout_button', None)
        if button is not None:
            studio_session = (self._target is not None and self._process is not None
                              and self._process.poll() is None)
            studio_ready = (studio_session and self._attached is not None
                            and self._attached.attached)
            sakura_ready = self.sakura_attached()
            # The button is part of the Studio header even during HWND attach:
            # do not make it vanish simply because native reparenting briefly
            # reports detached. The action remains disabled until safe.
            button.setVisible(bool(sakura_ready or studio_session))
            button.setEnabled(bool((studio_ready or sakura_ready)
                                   and not self._studio_popout_pending
                                   and not self._studio_dock_pending))
            button.setToolTip('Studioを外に出す（編集状態を保持）' if studio_ready
                              else 'Studioの収容が完了すると外に出せます' if studio_session
                              else 'サクラエディタを外に出す（終了しません）')
        if getattr(self, 'close_button', None) is not None:
            self.close_button.setToolTip(
                'サクラエディタへ通常終了を要求（未保存時はエディタ側で確認）'
                if self.sakura_attached() else '第3列を隠す（編集状態を保持）')

    def _explain_sakura_switch_blocked(self):
        self.launcher.show_launch_notice(
            QMessageBox.Icon.Information, 'サクラエディタを収容中',
            'サクラエディタは第3列に収容中です。\n'
            '他のプレビューに切り替えるには、右上の「外に出す」か「×」を押してください。')

    def pop_out_selected(self):
        """Use the same Browser external-arrow icon for either native editor."""
        if self.sakura_attached():
            return self.pop_out_sakura()
        return self.pop_out_studio()

    def pop_out_studio(self):
        """Release Studio's Launch-owner guard BEFORE detaching its HWND.

        The private pipe command requires the matching, rebuilt Studio source.
        An older NativeShell replies with ERROR and remains safely docked.
        """
        if (self._studio_popout_pending or self._launch_switch_pending is not None
                or self._attached is None or not self._attached.attached
                or self._process is None or self._process.poll() is not None
                or not self._launch_pipe_token):
            return False
        self._studio_popout_pending = True
        self._sync_popout_button()
        token = self._launch_pipe_token

        def request_release():
            reply = 'ERROR: Studioへの接続に失敗しました'
            address = r'\\.\pipe\frb_studio_launch_' + token
            for attempt in range(24):
                try:
                    with open(address, 'r+b', buffering=0) as channel:
                        channel.write(b'@FRB_LAUNCH_RELEASE@\n')
                        response = channel.readline()
                        reply = response.decode('utf-8', errors='replace').strip() if response else 'ERROR: 応答がありません'
                    break
                except OSError as exc:
                    reply = 'ERROR: ' + str(exc)
                    if attempt != 23:
                        time.sleep(0.15)
            self._studio_popout_ack.emit(reply)

        threading.Thread(target=request_release, name='FRBStudioPopout', daemon=True).start()
        return True

    def _finish_studio_popout(self, reply):
        if not self._studio_popout_pending:
            return
        self._studio_popout_pending = False
        if reply != 'OK':
            self.status_label.setText('Studioの外出しを中止しました。\n'
                'Studio最新版のNativeShell再ビルドが必要な場合があります。\n' + reply)
            self.status_label.show()
            self._sync_popout_button()
            return
        attached = self._attached
        try:
            attached.detach(foreground=True, show_window=True)
        except (OSError, RuntimeError, ValueError) as exc:
            # Studio has already acknowledged owner release. Never kill it.
            self.status_label.setText('Studioのウィンドウ復元に失敗しました: ' + str(exc))
            self.status_label.show()
            self._sync_popout_button()
            return
        self._attached = None
        self._process = None  # It is NO LONGER a Launch-owned session.
        self._target = None
        self._launch_pipe_token = None
        self._launch_switch_pending = None
        self._timer.stop()
        self._sync_popout_button()
        self.popout_requested.emit()
        return True

    def _restore_launch_focus_during_handoff(self):
        pending = self._external_pending
        if (pending is None or pending[0].app != 'obsidian'
                or self._attached is not None and self._external_key == pending[0].key):
            return
        owner = getattr(self, 'launcher', None)
        if owner is None or not owner.isVisible():
            return
        try:
            if not owner.isMinimized():
                owner.raise_()
                owner.activateWindow()
        except RuntimeError:
            return

    def _check_embedded_editor_health(self):
        """Hide an EMPTY Obsidian pane after its native HWND is destroyed.

        Do not infer document emptiness from a caption, and never close a
        desktop Obsidian process or an unsaved remaining tab.
        """
        if (self.isHidden() or self._external_pending is not None
                or self._external_key is None or self._external_key[0] != 'obsidian'):
            return
        attached = self._attached
        # An unsuccessful Obsidian handoff must not leave an empty third pane.
        if attached is None:
            self._external_key = None
            self._reset_obsidian_cli()
            self._sync_popout_button()
            self.popout_requested.emit()
            return
        try:
            alive = bool(attached.u.IsWindow(int(attached.hwnd)))
        except (OSError, RuntimeError, ValueError):
            alive = False
        if alive:
            return
        self._attached = None
        self._external_key = None
        self._reset_obsidian_cli()
        self._sync_popout_button()
        self.popout_requested.emit()

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
        if self._external_key is not None and self._external_key[0] == 'obsidian':
            getattr(self, '_reset_obsidian_cli', lambda: None)()
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
            getattr(self, '_obsidian_parked_vaults', {}).clear()
        if windows:
            from studio_win32_host import request_editor_window_close
            for hwnd, app in set(windows):
                try:
                    if app not in ('sakura', 'obsidian'):
                        request_editor_window_close(hwnd)
                    # Obsidian MAIN is borrowed, not Launch-owned. × restores
                    # it to desktop; NEVER send WM_CLOSE or lose unsaved work.
                    # Sakura likewise follows its own explicit close protocol.
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
        if target.app == 'obsidian':
            # The main window may predate this URI; it MUST NOT be picked by
            # find_new_editor_window(). Wait for the validated CLI handshake.
            if time.monotonic() - started > 17:
                self._fail_obsidian_main_dock('Obsidian本体の確認がタイムアウトしました。')
            return
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
        # The Obsidian main-window path returns above and has its own
        # CLI-probe timeout; this remaining legacy timer is for Sakura.
        timeout = 6 if switching_sakura else 25
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
        self._obsidian_main_probe_token = None
        self._sakura_switch_from = None
        old_obsidian_vault = (getattr(self, '_obsidian_cli_vault', None)
                              if self._external_key[0] == 'obsidian' else None)
        if self._external_key[0] == 'obsidian':
            getattr(self, '_reset_obsidian_cli', lambda: None)()
        attached = self._attached
        if attached is not None:
            try:
                attached.detach(foreground=False, show_window=False)
                self._external_parked[self._external_key] = attached.hwnd
                if old_obsidian_vault:
                    self._obsidian_parked_vaults[self._external_key] = old_obsidian_vault
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

    def _refresh_outer_frame_after_native_attach(self):
        """Rebuild Launch's rounded mask after a foreign WinForms HWND docks.

        Native SetParent can invalidate the frame composition on the first
        preview. This is presentation-only; never change splitter geometry,
        Studio ownership, focus, or the selected document here.
        """
        launcher = getattr(self, 'launcher', None)
        if launcher is None or not launcher.isVisible():
            return
        if getattr(launcher, '_size_drag', None):
            return  # A subsequent resize event already rebuilds the mask.
        launcher.clearMask()
        launcher.update_window_shape()
        launcher.update()

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
            hwnd = find_studio_main_window(self._process.pid, launch_preview=True)
            if hwnd:
                # Ensure Qt creates a native HWND before docking WinForms.
                self._attached = AttachedStudioWindow(hwnd, int(self.host.winId()))
                self._attached.resize(self.host.width(), self.host.height())
                self._timer.stop()
                self._notify_studio_docked()
                # Keep the loading label until Studio confirms it is docked
                # and has made its transparent preview visible inside Launch.
                self._sync_popout_button()
                # Qt/Win32 may recompose the outer mask after SetParent.  Run
                # on the next Qt event turn, after the native child is laid out.
                QTimer.singleShot(0, self._refresh_outer_frame_after_native_attach)
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

    def close_launch_owned_studio(self):
        """Close only the NativeShell launched with our private session token.

        This is called exclusively during Launch Quit, not Preview ×.
        A nested Qt event loop keeps the embedded Studio's unsaved dialog live.
        Cancellation/error leaves its process and window untouched.
        """
        process = self._process
        if process is None or process.poll() is not None:
            # Studio may have been parked to open Obsidian/Options.
            for candidate, _hwnd in self._parked.values():
                if candidate.poll() is None:
                    process = candidate
                    break
        if process is None or process.poll() is not None:
            return True
        if self._launch_switch_pending is not None:
            self.launcher.error('Studioのファイル切替中です。完了後にLaunchを終了してください。')
            return False
        token = self._launch_pipe_token
        if not token:
            self.launcher.error('Launch専用Studioの識別情報がありません。誤終了防止のためLaunchの終了を中止しました。')
            return False
        from studio_launch_lifecycle import close_owned_studio
        result = {}
        waiting = QEventLoop(self)
        timer = QTimer(self)
        timer.setSingleShot(True)

        def completed(reply):
            if 'reply' not in result:
                result['reply'] = reply
                waiting.quit()

        def timed_out():
            completed('ERROR: Studioの終了確認が時間切れになりました')

        self._launch_exit_completed.connect(completed)
        timer.timeout.connect(timed_out)
        try:
            def request():
                reply = close_owned_studio(process, token)
                self._launch_exit_completed.emit(reply)

            threading.Thread(target=request, name='FRBStudioLaunchClose', daemon=True).start()
            # Studio asks for user consent via its own unsaved-edit dialog.
            # The UI thread must remain responsive until that dialog resolves.
            timer.start(110000)
            if 'reply' not in result:
                waiting.exec()
        finally:
            timer.stop()
            self._launch_exit_completed.disconnect(completed)
            timer.deleteLater()
        if result.get('reply') == 'OK':
            if self._process is process:
                self._process = None
                self._attached = None  # Native HWND no longer exists.
                self._target = None
            self._parked = {key: value for key, value in self._parked.items()
                            if value[0] is not process}
            self._launch_pipe_token = None
            return True
        if result.get('reply') != 'CANCEL':
            self.launcher.error('Studioを正常終了できなかったため、Launchの終了を中止しました。\n'
                                + result.get('reply', 'ERROR: unknown'))
        return False

    def undock(self):
        """Restore all live Studio windows only when Launch itself exits."""
        self._timer.stop()
        self._external_timer.stop()
        self._sakura_close_timer.stop()
        self._embedded_health_timer.stop()
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
        self._launch_switch_pending = None
        self._launch_pipe_token = None
        if self._external_parked:
            from studio_win32_host import restore_parked_studio_window
            for hwnd in self._external_parked.values():
                try:
                    restore_parked_studio_window(hwnd)
                except (OSError, RuntimeError, ValueError):
                    pass
            self._external_parked.clear()
        getattr(self, '_obsidian_parked_vaults', {}).clear()
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
