"""Commander keyboard lane, disabled-action guard, popup isolation and Qt acceptance."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'src/commander/window.py'


def _probe_class():
    # Execute production methods without Qt; no duplicate navigation algorithm.
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CommanderWindow')
    names = {'_move_horizontal_focus', 'eventFilter'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    class Base:
        def eventFilter(self, obj, event):
            return False
    class Widget:
        def __init__(self):
            self.enabled = True
            self.focus = Mock()
            self.click = Mock()
        def isEnabled(self):
            return self.enabled
        def setFocus(self, reason):
            self.focus(reason)
    keys = NS(**{f'Key_{k}': k for k in ('Left', 'Right', 'Return', 'Enter', 'Escape', 'Down', 'Up', 'Slash')})
    types = NS(**{k: k for k in ('MouseButtonPress', 'Move', 'Resize', 'KeyPress', 'FocusIn')})
    qt = NS(Key=keys, FocusReason=NS(OtherFocusReason=1), KeyboardModifier=NS(ControlModifier=1))
    env = {'Base': Base, 'Qt': qt, 'QEvent': NS(Type=types), 'QWidget': Widget}
    module = ast.Module(body=[ast.ClassDef(name='Probe', bases=[ast.Name(id='Base', ctx=ast.Load())],
                         keywords=[], body=methods, decorator_list=[])], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), 'exec'), env)
    p = env['Probe']()
    p._event_filter_ready = True
    p.breadcrumb_frame, p.copy_button, p.run_button, p.search, p.listbox = [Widget() for _ in range(5)]
    p.candidate_popup = NS(isVisible=lambda: False)
    p.picking_step = None
    p._file_picker_pending = p._confirming = False
    p.active_steps = lambda: [1, 2, 3]
    p.focus_index = 0
    p.current = p.breadcrumb_frame
    p.focus_breadcrumb = lambda: setattr(p, 'current', p.breadcrumb_frame)
    for button in (p.copy_button, p.run_button):
        button.focus.side_effect = lambda reason, b=button: setattr(p, 'current', b)
    p._paint_breadcrumb_focus = Mock()
    p.open_selection = Mock()
    p.run_command = Mock()
    p.close = Mock()
    p.close_candidates = Mock()
    p._accept_choice = Mock()
    return p


def _key(p, key, *, modifiers=0, obj=None):
    event = NS(type=lambda: 'KeyPress', key=lambda: key, modifiers=lambda: modifiers)
    return p.eventFilter(p.current if obj is None else obj, event)


def test_bidirectional_bounded_lane_and_activation():
    p = _probe_class()
    assert _key(p, 'Left') and p.focus_index == 0
    for i in (1, 2):
        assert _key(p, 'Right') and p.current is p.breadcrumb_frame and p.focus_index == i
    assert _key(p, 'Right') and p.current is p.copy_button
    p._paint_breadcrumb_focus.assert_called_with(False)
    assert _key(p, 'Return')
    p.copy_button.click.assert_called_once_with()
    p.run_button.click.assert_not_called()
    assert _key(p, 'Right') and p.current is p.run_button
    assert _key(p, 'Right') and p.current is p.run_button
    assert _key(p, 'Enter')
    p.run_button.click.assert_called_once_with()
    assert _key(p, 'Left') and p.current is p.copy_button
    assert _key(p, 'Left') and p.current is p.breadcrumb_frame and p.focus_index == 2
    assert _key(p, 'Left') and p.focus_index == 1
    p.open_selection.assert_not_called()
    assert _key(p, 'Down')
    p.open_selection.assert_called_once_with()


def test_disabled_actions_and_active_picker_are_not_navigation_targets():
    p = _probe_class()
    p.focus_index = 2
    p.copy_button.enabled = p.run_button.enabled = False
    assert _key(p, 'Right') and p.current is p.breadcrumb_frame and p.focus_index == 2
    p.copy_button.enabled = p.run_button.enabled = True
    for attr in ('_file_picker_pending', '_confirming'):
        setattr(p, attr, True)
        assert _key(p, 'Right') and p.current is p.breadcrumb_frame
        setattr(p, attr, False)
    p.candidate_popup.isVisible = lambda: True
    assert _key(p, 'Right') and p.current is p.breadcrumb_frame
    p.candidate_popup.isVisible = lambda: False
    p.picking_step = {'input': 'single_choice'}
    assert _key(p, 'Right') and p.current is p.breadcrumb_frame
    # Popup Right still commits a choice; Left still closes the popup.
    assert _key(p, 'Right', obj=p.search)
    p._accept_choice.assert_called_once_with()
    assert _key(p, 'Left', obj=p.search)
    p.close_candidates.assert_called_once_with()


def test_ctrl_enter_does_not_copy_and_focus_highlight_moves():
    p = _probe_class()
    p.focus_index = 2
    _key(p, 'Right')
    assert _key(p, 'Return', modifiers=1)
    p.run_command.assert_called_once_with()
    p.copy_button.click.assert_not_called()
    p.eventFilter(p.copy_button, NS(type=lambda: 'FocusIn'))
    p._paint_breadcrumb_focus.assert_called_with(False)
    p.eventFilter(p.breadcrumb_frame, NS(type=lambda: 'FocusIn'))
    p._paint_breadcrumb_focus.assert_called_with(True)


def test_qt_navigation_copy_focus_and_run_confirmation(tmp_path):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    import json
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
    from commander.window import CommanderWindow
    from commander.viewdef import build_command
    app = QApplication.instance() or QApplication([])
    owner = QWidget()
    owner.ask_remote_confirmation = Mock(return_value=QMessageBox.StandardButton.No)
    owner.show()
    script = tmp_path / 'Export-DiffToJson.ps1'
    script.write_text('param()\n', encoding='utf-8')
    definition = json.loads((SOURCE.parents[2] / 'examples/commander/Export-DiffToJson.viewdef').read_text(encoding='utf-8'))
    window = CommanderWindow(owner, script, definition, tmp_path)
    try:
        window.show()
        window.activateWindow()
        window.focus_breadcrumb()
        app.processEvents()
        assert not window.copy_button.isEnabled()
        QTest.keyClick(window.breadcrumb_frame, Qt.Key.Key_Right)
        assert window.focus_index == 0
        window.values.update(source='commit_range', range='main..HEAD')
        window.refresh_breadcrumbs()
        window.focus_breadcrumb()
        for _ in range(2):
            QTest.keyClick(window.breadcrumb_frame, Qt.Key.Key_Right)
        assert window.copy_button.hasFocus()
        assert all('#4b85cb' not in b.styleSheet() for b in window.crumb_buttons)
        QTest.keyClick(window.copy_button, Qt.Key.Key_Return)
        assert app.clipboard().text() == build_command(definition, window.values, script).powershell_text()
        assert window.copy_button.hasFocus()
        assert window.process is None
        owner.ask_remote_confirmation.assert_not_called()
        QTest.keyClick(window.copy_button, Qt.Key.Key_Right)
        assert window.run_button.hasFocus()
        QTest.keyClick(window.run_button, Qt.Key.Key_Left)
        assert window.copy_button.hasFocus()
        QTest.keyClick(window.copy_button, Qt.Key.Key_Left)
        assert window.breadcrumb_frame.hasFocus() and window.focus_index == 1
        assert '#4b85cb' in window.crumb_buttons[1].styleSheet()
        QTest.keyClick(window.breadcrumb_frame, Qt.Key.Key_Right)
        QTest.keyClick(window.copy_button, Qt.Key.Key_Right)
        QTest.keyClick(window.run_button, Qt.Key.Key_Return)
        owner.ask_remote_confirmation.assert_called_once()
        assert window.process is None
    finally:
        window.close()
        owner.close()
