"""Third Files column: host actual FRB Studio and Launch Option Settings.

The Preview × hides the panel, not the C# application. Live Studio sessions
stay in memory with their unsaved changes; switching targets parks old windows
invisibly. Launch exit restores all live Studio windows to the desktop.
"""
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QWidget, QLabel, QToolButton, QVBoxLayout,
                               QHBoxLayout, QSizePolicy, QStackedWidget)
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
        self.close_button.setToolTip('第3列を隠す（エディターの編集状態は保持）')
        self.close_button.clicked.connect(self.close_requested.emit)
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
        """Launch and dock a NEW Sakura/Obsidian window, never an old HWND."""
        self.content_stack.setCurrentWidget(self.host)
        if self._external_key == target.key and (self._attached or self._external_pending):
            if self._attached:
                self._attached.resize(self.host.width(), self.host.height())
            return True
        self._park_current()  # also parks a preceding external editor
        if self._target is not None or self._external_key is not None:
            return False  # Failed to park: never overwrite an unsaved editor.
        self.title_label.setText(('Obsidian' if target.app == 'obsidian'
                                  else 'サクラエディタ') + ' — ' + Path(target.path).name)
        self.title_label.setToolTip(target.path)
        from studio_win32_host import AttachedStudioWindow
        previous = self._external_parked.pop(target.key, None)
        if previous:
            try:
                self._attached = AttachedStudioWindow(previous, int(self.host.winId()))
                self._attached.resize(self.host.width(), self.host.height())
                self._external_key = target.key
                self.status_label.hide()
                return True
            except (OSError, RuntimeError, ValueError):
                self._attached = None  # Native window was closed while parked.
        try:
            from external_win32_host import snapshot_editor_windows
            baseline = snapshot_editor_windows(target.app)
            launched_pid = None
            if target.app == 'obsidian':
                import os
                from external_preview_route import obsidian_open_uri
                os.startfile(obsidian_open_uri(target.path))
            elif target.app == 'sakura':
                from external_preview_route import external_start_command
                process = subprocess.Popen(external_start_command(target),
                                           cwd=str(Path(target.executable).parent))
                launched_pid = process.pid
            else:
                raise ValueError('未知の外部エディターです')
        except (OSError, ValueError, RuntimeError) as exc:
            self.status_label.setText('エディターを開けませんでした: ' + str(exc))
            self.status_label.show()
            return False
        self._external_key = target.key
        self._external_pending = (target, baseline, launched_pid, time.monotonic())
        self.status_label.setText(
            '外部エディターの新しいウィンドウを待っています…\n'
            '既存ウィンドウを奪わず、安全に収容できた場合だけ表示します')
        self.status_label.show()
        self._external_timer.start()
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
        try:
            from external_win32_host import find_new_editor_window
            hwnd = find_new_editor_window(target, baseline, launched_pid)
            if hwnd:
                from studio_win32_host import AttachedStudioWindow
                self._attached = AttachedStudioWindow(hwnd, int(self.host.winId()))
                self._attached.resize(self.host.width(), self.host.height())
                self.status_label.hide()
                self._external_pending = None
                self._external_timer.stop()
                return
        except (OSError, RuntimeError, ValueError) as exc:
            self._external_timer.stop()
            self._external_pending = None
            self.status_label.setText('第3列への収容に失敗しました。外側のアプリで編集できます。\n' + str(exc))
            self.status_label.show()
            return
        if time.monotonic() - started > 30:
            self._external_timer.stop()
            self._external_pending = None
            self.status_label.setText(
                '新しい編集ウィンドウを特定できませんでした。\n'
                '既存アプリの画面は安全のため収容していません。\n'
                'Obsidianの場合はVault登録を確認してください。')
            self.status_label.show()

    def _park_external(self):
        if self._external_key is None:
            return
        self._external_timer.stop()
        self._external_pending = None
        attached = self._attached
        if attached is not None:
            try:
                attached.detach(foreground=False, show_window=False)
            except (OSError, RuntimeError):
                return  # Can't safely detach; don't discard its state.
            self._external_parked[self._external_key] = attached.hwnd
            self._attached = None
        self._external_key = None

    def _show_target_title(self, target):
        name = 'Launch メニュー設定' if len(target) > 3 else Path(target[0]).name
        self.title_label.setText('FRB Studio — ' + name)
        self.title_label.setToolTip(target[0])

    def open_options(self, launch_home, state_dir, studio_root):
        """Reuse the existing Qt WebEngine + Node save bridge as a child pane."""
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
