"""Launch-owned FRB Commander with breadcrumb-anchored searchable choice windows."""
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, Qt, QProcess, QPoint
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget)

from commander.viewdef import (build_command, read_viewdef,
    resolve_initial_directory, visible_steps)


def launch_commander(launcher, script, *, workspace_root=None):
    script = Path(script).resolve()
    definition = read_viewdef(script)
    previous = getattr(launcher, '_commander_dialog', None)
    if previous is not None:
        try:
            if previous.isVisible():
                previous.raise_()
                previous.activateWindow()
                previous.focus_breadcrumb()
                return previous  # One Commander interaction at a time.
        except RuntimeError:
            pass
    dialog = CommanderWindow(launcher, script, definition, workspace_root)
    launcher._commander_dialog = dialog
    dialog.finished.connect(lambda result, window=dialog:
        setattr(launcher, '_commander_dialog', None)
        if getattr(launcher, '_commander_dialog', None) is window else None)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    QTimer.singleShot(0, dialog.focus_breadcrumb)
    return dialog


class CommanderWindow(QDialog):
    """Keyboard: ←→ steps/actions, ↓ edit, ↑↓ browse, Enter activate, Ctrl+Enter run."""

    def __init__(self, launcher, script, definition, workspace_root):
        super().__init__(launcher)
        self.launcher = launcher
        self.script = Path(script).resolve()
        self.definition = definition
        self.workspace_root = workspace_root
        self.values = {}
        self.focus_index = 0
        self.picking_step = None
        self.process = None
        self._file_picker_pending = False
        self._picker_session = 0
        self._confirming = False
        self.setWindowTitle('FRB Commander — ' + definition['title'])
        # Owned by Launch, but do not independently force global topmost.
        # The common dialog owns confirmation z-order relative to this window.
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumWidth(620)
        self.resize(740, 180)
        self.setStyleSheet('''
            QDialog { background: #f6f8fb; color: #192a3a; }
            QFrame#commanderBread { background: #ffffff; border: 1px solid #ccd5df;
                                   border-radius: 8px; }
            QLabel#commanderHint { color: #617185; }
            QFrame#commanderCandidatesWindow {
                border: 1px solid #8faaca; border-radius: 7px;
                background: #ffffff;
            }
            QListWidget#commanderCandidates { border: 0; border-radius: 5px;
                          background: #ffffff; padding: 3px; }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background: #d7e8ff; color: #18283c; }
            QLineEdit { border: 1px solid #91a8c0; border-radius: 6px;
                        background: #ffffff; padding: 7px; }
            QPushButton { padding: 7px 11px; }
        ''')

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 13, 14, 13)
        top = QHBoxLayout()
        top.addWidget(QLabel('⌨  FRB Commander  |  ' + definition['title']))
        top.addStretch()
        top.addWidget(QLabel(self.script.name))
        root.addLayout(top)

        self.breadcrumb_frame = QFrame(self)
        self.breadcrumb_frame.setObjectName('commanderBread')
        self.breadcrumb_frame.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_frame)
        self.breadcrumb_layout.setContentsMargins(9, 9, 9, 9)
        self.breadcrumb_layout.setSpacing(6)
        root.addWidget(self.breadcrumb_frame)

        self.hint = QLabel('← → 項目・ボタン移動  /  ↓・クリック 候補表示  /  Enter 決定  /  Ctrl+Enter 実行', self)
        self.hint.setObjectName('commanderHint')
        root.addWidget(self.hint)

        # Match Keyboard Ex: an activatable native Tool owns the real edit
        # (including Windows IME) and the candidate list. The main layout
        # contains neither, so expanding/filtering never reflows Commander.
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        self.candidate_popup = QFrame(self, flags)
        self.candidate_popup.setObjectName('commanderCandidatesWindow')
        candidate_layout = QVBoxLayout(self.candidate_popup)
        candidate_layout.setContentsMargins(7, 7, 7, 7)
        candidate_layout.setSpacing(5)
        self.popup_hint = QLabel('↑ ↓ 候補移動 / Enter・→ 確定 / Esc・← 閉じる', self.candidate_popup)
        self.popup_hint.setObjectName('commanderHint')
        candidate_layout.addWidget(self.popup_hint)
        self.search = QLineEdit(self.candidate_popup)
        self.search.setPlaceholderText('候補を検索…')
        self.search.textChanged.connect(self._filter_candidates)
        candidate_layout.addWidget(self.search)
        self.listbox = QListWidget(self.candidate_popup)
        self.listbox.setObjectName('commanderCandidates')
        self.listbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.listbox.itemClicked.connect(lambda item: self._accept_choice())
        candidate_layout.addWidget(self.listbox, stretch=1)
        self.text_confirm = QPushButton('確定  Enter', self.candidate_popup)
        self.text_confirm.setAutoDefault(False)
        self.text_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.text_confirm.clicked.connect(self._accept_choice)
        candidate_layout.addWidget(self.text_confirm)
        self.text_confirm.hide()
        self.candidate_popup.hide()
        self._popup_mouse_guard = False

        bar = QHBoxLayout()
        self.status = QLabel('選択を始めてください', self)
        self.status.setObjectName('commanderHint')
        bar.addWidget(self.status, stretch=1)
        self.copy_button = QPushButton('コマンドコピー', self)
        self.copy_button.setAutoDefault(False)
        self.copy_button.setToolTip('PowerShellで再実行できるコマンドをコピーします（実行しません）')
        self.copy_button.clicked.connect(self.copy_command)
        bar.addWidget(self.copy_button)
        self.run_button = QPushButton('実行  Ctrl+Enter', self)
        self.run_button.setAutoDefault(False)
        self.run_button.clicked.connect(self.run_command)
        bar.addWidget(self.run_button)
        for button in (self.copy_button, self.run_button):
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setStyleSheet('QPushButton:focus { background: #d5e7ff; '
                                 'color: #192a3a; border: 2px solid #4b85cb; '
                                 'border-radius: 5px; padding: 6px 10px; }')
        QWidget.setTabOrder(self.breadcrumb_frame, self.copy_button)
        QWidget.setTabOrder(self.copy_button, self.run_button)
        root.addLayout(bar)

        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(1500)
        self.output.hide()
        root.addWidget(self.output)
        self.run_shortcut = QShortcut(QKeySequence('Ctrl+Return'), self)
        self.run_shortcut.activated.connect(self.run_command)
        self.keypad_run_shortcut = QShortcut(QKeySequence('Ctrl+Enter'), self)
        self.keypad_run_shortcut.activated.connect(self.run_command)
        self.crumb_buttons = []
        self.refresh_breadcrumbs()
        # Install only once all event-filter dependencies exist. Qt delivers
        # synchronous ChildAdded/Move/Resize events during widget construction.
        self.breadcrumb_frame.installEventFilter(self)
        self.copy_button.installEventFilter(self)
        self.run_button.installEventFilter(self)
        self.search.installEventFilter(self)
        self.listbox.installEventFilter(self)
        self._event_filter_ready = True

    def active_steps(self):
        return visible_steps(self.definition, self.values)

    def focus_breadcrumb(self):
        if not self.isVisible():
            return
        self.breadcrumb_frame.setFocus(Qt.FocusReason.OtherFocusReason)
        self._paint_breadcrumb_focus(True)

    def refresh_breadcrumbs(self):
        steps = self.active_steps()
        self.focus_index = max(0, min(self.focus_index, len(steps) - 1))
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        self.crumb_buttons.clear()
        for index, step in enumerate(steps):
            value = self.values.get(step['id'])
            if value:
                if step['input'] == 'file_path':
                    text = f'{step["label"]}: {Path(value).name}'
                elif step['input'] == 'single_choice':
                    text = next((c['label'] for c in step['choices']
                                 if c['value'] == value), value)
                else:
                    text = str(value)
            else:
                text = step['label'] + '：未選択'
            label = QPushButton(text, self.breadcrumb_frame)
            label.setAutoDefault(False)
            label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setToolTip(str(value) if value else 'クリック / ↓ で選択')
            label.clicked.connect(lambda checked=False, i=index: self._click_breadcrumb(i))
            self.crumb_buttons.append(label)
            self.breadcrumb_layout.addWidget(label)
            if index < len(steps)-1:
                sep = QLabel('›', self.breadcrumb_frame)
                sep.setStyleSheet('color: #6b7b8b;')
                self.breadcrumb_layout.addWidget(sep)
        self.breadcrumb_layout.addStretch(1)
        self._update_command_buttons()
        self._paint_breadcrumb_focus(not (self.copy_button.hasFocus() or self.run_button.hasFocus()))
        if self.ready():
            self.status.setText('選択完了：コピーまたは Ctrl+Enter で実行確認')

    def _paint_breadcrumb_focus(self, show):
        # The anchor index stays valid for the candidate popup, even while an
        # action has keyboard focus. Only one target should look selected.
        for index, label in enumerate(self.crumb_buttons):
            active = show and index == self.focus_index
            label.setStyleSheet('background: #d5e7ff; border: 2px solid #4b85cb; '
                                'border-radius: 5px; padding: 7px;' if active else
                                'background: #edf1f5; border: 2px solid transparent; '
                                'border-radius: 5px; padding: 7px;')

    def _move_horizontal_focus(self, origin, direction):
        """One bounded navigation lane; disabled actions are not tab stops."""
        if (self.candidate_popup.isVisible() or self.picking_step is not None
                or self._file_picker_pending or self._confirming):
            return
        targets = [(self.breadcrumb_frame, i) for i in range(len(self.active_steps()))]
        targets.extend((button, None) for button in (self.copy_button, self.run_button)
                       if button.isEnabled())
        current = (origin, self.focus_index if origin is self.breadcrumb_frame else None)
        if current not in targets:
            return
        position = targets.index(current)
        widget, index = targets[max(0, min(len(targets) - 1, position + direction))]
        if widget is self.breadcrumb_frame:
            self.focus_index = index
            self.focus_breadcrumb()
        else:
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
            self._paint_breadcrumb_focus(False)

    def _update_command_buttons(self):
        enabled = (self.ready() and not self._running() and not self._confirming
                   and self.picking_step is None and not self._file_picker_pending)
        self.copy_button.setEnabled(enabled)
        self.run_button.setEnabled(enabled)

    def ready(self):
        return all(isinstance(self.values.get(s['id']), str)
                   and bool(self.values[s['id']].strip()) for s in self.active_steps())

    def _running(self):
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def eventFilter(self, obj, event):
        if not getattr(self, "_event_filter_ready", False):
            return super().eventFilter(obj, event)
        # A Tool window does not get QMenu's native click-away behavior.
        # Observe outside presses without consuming the target's click.
        if (event.type() == QEvent.Type.MouseButtonPress and
                self.candidate_popup.isVisible() and isinstance(obj, QWidget)):
            if obj is not self.candidate_popup and not self.candidate_popup.isAncestorOf(obj):
                self.close_candidates(restore_focus=False)
        if (obj is self.breadcrumb_frame and event.type() in
                (QEvent.Type.Move, QEvent.Type.Resize) and self.candidate_popup.isVisible()):
            QTimer.singleShot(0, self._place_candidate_popup)
        main_targets = (self.breadcrumb_frame, self.copy_button, self.run_button)
        if event.type() == QEvent.Type.FocusIn and obj in main_targets:
            self._paint_breadcrumb_focus(obj is self.breadcrumb_frame)
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)
        key = event.key()
        if obj in main_targets:
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                self._move_horizontal_focus(obj, -1 if key == Qt.Key.Key_Left else 1)
                return True
            if obj in (self.copy_button, self.run_button):
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        self.run_command()
                    elif obj.isEnabled():
                        obj.click()
                    return True
                # Space retains QPushButton's native activation; Esc closes.
                if key == Qt.Key.Key_Escape:
                    self.close()
                    return True
        if obj is self.breadcrumb_frame:
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Slash, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.open_selection()
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        elif (obj in (self.search, self.listbox) and self.picking_step is not None):
            if key == Qt.Key.Key_Escape or (key == Qt.Key.Key_Left and self.picking_step['input'] == 'single_choice'):
                self.close_candidates()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) or (key == Qt.Key.Key_Right and self.picking_step['input'] == 'single_choice'):
                # Ctrl+Enter remains the dedicated run shortcut.
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self.run_command()
                    return True
                self._accept_choice()
                return True
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                count = self.listbox.count()
                if count:
                    idx = self.listbox.currentRow()
                    self.listbox.setCurrentRow(max(0, min(count-1,
                        idx + (1 if key == Qt.Key.Key_Down else -1))))
                return True
            if obj is self.listbox and event.text() and event.text().isprintable():
                self.search.setText(self.search.text() + event.text())
                self.search.setFocus()
                return True
        return super().eventFilter(obj, event)

    def _click_breadcrumb(self, index):
        if self._running() or not 0 <= index < len(self.active_steps()):
            return
        self.focus_index = index
        self.refresh_breadcrumbs()
        self.focus_breadcrumb()
        self.open_selection()

    def _active_crumb(self):
        if 0 <= self.focus_index < len(self.crumb_buttons):
            return self.crumb_buttons[self.focus_index]
        return self.breadcrumb_frame

    def open_selection(self):
        if self._running() or not self.isVisible():
            return
        steps = self.active_steps()
        if not steps:
            return
        step = steps[self.focus_index]
        if step['input'] == 'file_path':
            self.close_candidates()
            self.open_file_picker(step)
            return
        if self._file_picker_pending:
            # A late close from Keyboard Ex must not steal the new popup focus.
            self._file_picker_pending = False
            self._picker_session += 1
        self.picking_step = step
        self._update_command_buttons()
        is_choice = step['input'] == 'single_choice'
        self.popup_hint.setText('↑ ↓ 候補移動 / Enter・→ 確定 / Esc・← 閉じる' if is_choice
                                else 'Enter 確定 / Esc 閉じる')
        self.listbox.setVisible(is_choice)
        self.text_confirm.setVisible(not is_choice)
        self.search.setPlaceholderText('候補を検索…' if is_choice else step['label'] + ' を入力')
        self.search.setText('' if is_choice else self.values.get(step['id'], ''))
        self._filter_candidates(self.search.text())
        self._show_candidate_popup()
        if not is_choice:
            self.search.selectAll()

    def _filter_candidates(self, query):
        step = self.picking_step
        if not step:
            return
        self.listbox.clear()
        if step['input'] == 'single_choice':
            for choice in step['choices']:
                if query.casefold() in (choice['label'] + ' ' + choice.get('hint', '')).casefold():
                    item = QListWidgetItem(choice['label'] +
                        ('  — ' + choice['hint'] if choice.get('hint') else ''))
                    item.setData(Qt.ItemDataRole.UserRole, choice['value'])
                    self.listbox.addItem(item)
            if self.listbox.count():
                self.listbox.setCurrentRow(0)
        # Filtering only changes rows, never popup geometry or focus.

    def _show_candidate_popup(self):
        if not self.isVisible() or self.picking_step is None:
            return
        self.breadcrumb_layout.activate()
        layout = self.candidate_popup.layout()
        layout.activate()
        if self.picking_step['input'] == 'single_choice':
            rows = len(self.picking_step['choices'])
            row_height = max(33, self.listbox.sizeHintForRow(0) + 6) if self.listbox.count() else 33
            list_height = max(48, min(236, rows * row_height + 10))
            popup_height = self.popup_hint.sizeHint().height() + self.search.sizeHint().height() + list_height + 24
        else:
            popup_height = layout.sizeHint().height()
        self.candidate_popup.resize(max(420, min(520, self.breadcrumb_frame.width())), popup_height)
        self._place_candidate_popup()
        self.candidate_popup.show()
        self.candidate_popup.raise_()
        self._focus_popup_search()
        QTimer.singleShot(0, self._focus_popup_search)
        if not self._popup_mouse_guard:
            QApplication.instance().installEventFilter(self)
            self._popup_mouse_guard = True

    def _focus_popup_search(self):
        if self.picking_step is not None and self.candidate_popup.isVisible():
            self.candidate_popup.activateWindow()
            self.search.setFocus(Qt.FocusReason.OtherFocusReason)

    def _place_candidate_popup(self):
        """Anchor to the selected crumb, not the popup's own search edit."""
        if not self.isVisible() or self.picking_step is None:
            return
        crumb = self._active_crumb()
        origin = crumb.mapToGlobal(QPoint(0, crumb.height() + 4))
        screen = (QApplication.screenAt(crumb.mapToGlobal(QPoint(0, 0))) or
                  QApplication.primaryScreen())
        if screen is None:
            self.candidate_popup.move(origin)
            return
        bounds = screen.availableGeometry()
        width = min(self.candidate_popup.width(), bounds.width())
        height = min(self.candidate_popup.height(), bounds.height())
        self.candidate_popup.resize(width, height)
        x = max(bounds.left(), min(origin.x(), bounds.right() - width + 1))
        y = origin.y()
        if y + height > bounds.bottom() + 1:
            above = crumb.mapToGlobal(QPoint(0, -height - 4)).y()
            y = max(bounds.top(), above if above >= bounds.top() else bounds.bottom() - height + 1)
        self.candidate_popup.move(x, y)

    def _accept_choice(self):
        step = self.picking_step
        if step is None:
            return
        if step['input'] == 'single_choice':
            item = self.listbox.currentItem()
            if item is None:
                return
            value = item.data(Qt.ItemDataRole.UserRole)
        else:
            value = self.search.text().strip()
            if not value:
                return
        self.accept_value(step['id'], value)

    def close_candidates(self, *, restore_focus=True):
        self.picking_step = None
        if self._popup_mouse_guard:
            QApplication.instance().removeEventFilter(self)
            self._popup_mouse_guard = False
        self.candidate_popup.hide()
        self.search.clear()
        self._update_command_buttons()
        if restore_focus and self.isVisible():
            self.activateWindow()
            self.focus_breadcrumb()

    def accept_value(self, step_id, value):
        original = self.values.get(step_id)
        self.close_candidates()
        self.values[step_id] = str(value)
        if original != value and step_id == 'source':
            for key in list(self.values):
                if key != 'source':
                    self.values.pop(key, None)
        elif original != value and step_id == 'from_file':
            # A different source directory changes where the next picker starts.
            self.values.pop('to_file', None)
        steps = self.active_steps()
        missing = next((i for i, s in enumerate(steps) if not self.values.get(s['id'])), None)
        if missing is None:
            self.focus_index = next((i for i,s in enumerate(steps) if s['id']==step_id), 0)
            self.refresh_breadcrumbs()
            self.focus_breadcrumb()
        else:
            self.focus_index = missing
            self.refresh_breadcrumbs()
            QTimer.singleShot(0, self.open_selection)

    def open_file_picker(self, step):
        from slash_exp_navigation import physical_folder_source, popup_exp_navigator
        view = getattr(self.launcher, 'expanded_view', None)
        panel = (self.launcher._current_remote_files_exp()
                 if hasattr(self.launcher, '_current_remote_files_exp') else None)
        if panel is None and view is not None:
            panel = getattr(view, 'embedded_files_exp', None)
        if panel is None:
            self.status.setText('Keyboard ExのFiles Expが見つかりません')
            self.focus_breadcrumb()
            return
        try:
            directory = resolve_initial_directory(step, self.values,
                script=self.script, workspace_root=self.workspace_root)
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        source = physical_folder_source(self.launcher, str(directory))
        if source is None:
            self.status.setText('選択開始フォルダーが見つかりません: ' + str(directory))
            return
        self._picker_session += 1
        session_id = self._picker_session
        self._file_picker_pending = True
        self._update_command_buttons()
        self.status.setText(f'Keyboard Ex: {step["label"]}を選択 ({directory})')
        crumb = self._active_crumb()
        anchor = crumb.mapToGlobal(QPoint(0, crumb.height() + 4))
        selected_step_id = step['id']
        try:
            opened = popup_exp_navigator(self.launcher, panel, anchor,
                source_item=source,
                first_column_width=max(300, min(self.width() - 60, 480)),
                on_file_selected=lambda chosen, item_id=selected_step_id:
                    self._file_chosen(item_id, chosen))
            if not opened:
                self._file_picker_pending = False
                self._update_command_buttons()
                self.status.setText('このフォルダーに選択できるファイル・フォルダーがありません')
                return
            menu = getattr(self.launcher, '_slash_exp_navigation_menu', None)
            if menu is not None:
                menu.aboutToHide.connect(lambda token=session_id: self._file_picker_closed(token))
        except (OSError, ValueError, RuntimeError) as exc:
            self._file_picker_pending = False
            self._update_command_buttons()
            self.status.setText('Keyboard Ex起動エラー: ' + str(exc))

    def _file_chosen(self, step_id, filename):
        self._file_picker_pending = False
        if self.isVisible():
            self.accept_value(step_id, filename)

    def _file_picker_closed(self, session_id):
        # Stale close notifications from the first picker must never steal
        # focus from a second picker that opened immediately after selection.
        QTimer.singleShot(80, lambda token=session_id:
                          self._restore_after_file_picker(token))

    def _restore_after_file_picker(self, session_id):
        if (session_id == self._picker_session and
                self.isVisible() and self._file_picker_pending):
            self._file_picker_pending = False
            self._update_command_buttons()
            self.status.setText('ファイル選択をキャンセルしました。↓で再選択')
            self.activateWindow()
            self.focus_breadcrumb()

    def _selected_command(self):
        if self._running() or self._confirming:
            raise ValueError('実行中または確認応答中です')
        if self.picking_step is not None or self._file_picker_pending:
            raise ValueError('候補または入力を確定してください')
        return build_command(self.definition, self.values, self.script)

    def copy_command(self):
        try:
            command = self._selected_command()
            QApplication.clipboard().setText(command.powershell_text())
        except (ValueError, StopIteration, KeyError) as exc:
            self.status.setText('コピーできません: ' + str(exc))
            return
        self.status.setText('コマンドをクリップボードにコピーしました')
        # Keep focus on Copy so one Right key moves directly to Run.

    def run_command(self):
        if self._running() or self._confirming:
            return
        try:
            command = self._selected_command()
        except (ValueError, StopIteration, KeyError) as exc:
            self.status.setText('実行できません: ' + str(exc))
            return
        labels = []
        for step in self.active_steps():
            value = self.values.get(step['id'], '')
            if step['input'] == 'single_choice' and value:
                value = next(c['label'] for c in step['choices'] if c['value'] == value)
            labels.append(f'{step["label"]}: {value}')
        detail = ('\n'.join(labels) + '\n\n出力先の既存データは上書きされる可能性があります。'
                  '\n実行しますか？')
        self._confirming = True
        self._update_command_buttons()
        try:
            answer = self.launcher.ask_remote_confirmation(
                'FRB Commander — 実行確認', detail, owner=self)
        finally:
            self._confirming = False
            self._update_command_buttons()
        if answer != QMessageBox.StandardButton.Yes:
            self.focus_breadcrumb()
            return
        self.output.show()
        self.output.appendPlainText('実行開始: ' + self.script.name)
        self.status.setText('処理実行中...')
        self.process = QProcess(self)
        self.process.setProgram(command.program)
        self.process.setArguments(list(command.argv))
        self.process.setWorkingDirectory(command.working_directory)
        self.process.readyReadStandardOutput.connect(lambda: self._read_output(False))
        self.process.readyReadStandardError.connect(lambda: self._read_output(True))
        self.process.errorOccurred.connect(lambda error: self._process_error())
        self.process.finished.connect(self._process_finished)
        self.process.start()
        self._update_command_buttons()

    def _read_output(self, error):
        if self.process is None:
            return
        data = (self.process.readAllStandardError() if error
                else self.process.readAllStandardOutput())
        text = bytes(data).decode('utf-8', errors='replace').rstrip()
        if text:
            self.output.appendPlainText(text)

    def _process_error(self):
        if self.process:
            self.status.setText('実行エラー: ' + self.process.errorString())
            self.output.appendPlainText(self.process.errorString())
            self._update_command_buttons()

    def _process_finished(self, exit_code, exit_status):
        self._read_output(False)
        self._read_output(True)
        ok = exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit
        self.status.setText('実行完了 (終了コード 0)' if ok else
                            f'処理終了 (終了コード {exit_code}) — ログを確認してください')
        self.output.appendPlainText(self.status.text())
        self._update_command_buttons()
        self.focus_breadcrumb()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, 'candidate_popup') and self.candidate_popup.isVisible():
            self._place_candidate_popup()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'candidate_popup') and self.candidate_popup.isVisible():
            QTimer.singleShot(0, self._place_candidate_popup)

    def hideEvent(self, event):
        if hasattr(self, '_popup_mouse_guard'):
            self.close_candidates(restore_focus=False)
        super().hideEvent(event)

    def closeEvent(self, event):
        if self._confirming:
            event.ignore()
            return
        menu = getattr(self.launcher, '_slash_exp_navigation_menu', None)
        if (menu is not None and
                getattr(menu, '_file_selection_callback', None) is not None):
            try:
                menu.close()
            except RuntimeError:
                pass
        if self._running():
            self._confirming = True
            try:
                answer = self.launcher.ask_remote_confirmation(
                    '処理実行中',
                    '実行中のPowerShellを終了してCommanderを閉じますか？', owner=self)
            finally:
                self._confirming = False
                self._update_command_buttons()
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.process.kill()
            self.process.waitForFinished(2000)
        self.close_candidates(restore_focus=False)
        event.accept()
