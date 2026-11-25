"""Commander copy/execute contract and common dialog owner regression."""
import ast
import json
import os
from pathlib import Path
from subprocess import list2cmdline
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from commander.viewdef import build_command, build_argv, CommanderCommand

ROOT = Path(__file__).resolve().parents[1]


def method(file, cls, name):
    tree = ast.parse((ROOT / 'src' / file).read_text(encoding='utf-8'))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)


def load_functions(file, names, env, cls=None):
    tree = ast.parse((ROOT / 'src' / file).read_text(encoding='utf-8'))
    body = tree.body if cls is None else next(n.body for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == cls)
    selected = [n for n in body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(selected) == len(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), file, 'exec'), env)
    return env


@pytest.fixture
def command_inputs(tmp_path):
    folder = tmp_path / "日本語 空白's & $folder"
    folder.mkdir()
    script = folder / 'Export-DiffToJson.ps1'
    script.write_text('param()\n', encoding='utf-8')
    definition = json.loads((ROOT / 'examples/commander/Export-DiffToJson.viewdef').read_text(encoding='utf-8'))
    values = {'source': 'commit_range', 'range': 'main..HEAD "quoted" & $var\'s'}
    return script, definition, values


def test_same_program_argv_cwd_and_powershell_quoting(command_inputs):
    script, definition, values = command_inputs
    command = build_command(definition, values, script)
    assert command.program == 'powershell.exe'
    assert list(command.argv) == build_argv(definition, values, script)
    assert command.working_directory == str(script.parent)
    quoted_args = list2cmdline(command.argv).replace("'", "''")
    assert f"-ArgumentList '{quoted_args}'" in command.powershell_text()
    assert "-WorkingDirectory '" + str(script.parent).replace("'", "''") + "'" in command.powershell_text()
    assert command.powershell_text().endswith('-NoNewWindow -Wait')
    assert '-File' in command.argv
    assert values['range'] == command.argv[-1]


def test_empty_and_trailing_slash_argv_are_preserved():
    command = CommanderCommand('powershell.exe', ('', 'C:\\space path\\', 'a"b', "a'b"), 'C:\\')
    assert f"-ArgumentList '{list2cmdline(command.argv).replace(chr(39), chr(39)*2)}'" in command.powershell_text()


def test_copy_does_not_confirm_or_launch_and_failed_input_keeps_clipboard(command_inputs):
    script, definition, values = command_inputs
    clipboard = NS(setText=Mock())
    env = load_functions('commander/window.py', ['_selected_command', 'copy_command'],
                         {'build_command': build_command, 'QApplication': NS(clipboard=lambda: clipboard)}, 'CommanderWindow')
    window = NS(_running=lambda: False, _confirming=False, picking_step=None,
                _file_picker_pending=False, definition=definition, values=values, script=script,
                status=NS(setText=Mock()), focus_breadcrumb=Mock(),
                launcher=NS(ask_remote_confirmation=Mock()), process=None)
    window._selected_command = lambda: env['_selected_command'](window)
    env['copy_command'](window)
    clipboard.setText.assert_called_once_with(build_command(definition, values, script).powershell_text())
    window.launcher.ask_remote_confirmation.assert_not_called()
    assert window.process is None
    window._file_picker_pending = True
    env['copy_command'](window)
    assert clipboard.setText.call_count == 1
    window._file_picker_pending = False
    window.values = {'source': 'commit_range'}
    env['copy_command'](window)
    assert clipboard.setText.call_count == 1


def test_both_actions_share_command_spec_and_both_confirmations_have_commander_owner():
    for name in ('run_command', 'copy_command'):
        source = ast.unparse(method('commander/window.py', 'CommanderWindow', name))
        assert 'self._selected_command()' in source
    run = ast.unparse(method('commander/window.py', 'CommanderWindow', 'run_command'))
    assert 'setProgram(command.program)' in run
    assert 'setArguments(list(command.argv))' in run
    assert 'setWorkingDirectory(command.working_directory)' in run
    for name in ('run_command', 'closeEvent'):
        node = method('commander/window.py', 'CommanderWindow', name)
        call = next(n for n in ast.walk(node) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == 'ask_remote_confirmation')
        assert any(k.arg == 'owner' and isinstance(k.value, ast.Name) and k.value.id == 'self' for k in call.keywords)
    init = ast.unparse(method('commander/window.py', 'CommanderWindow', '__init__'))
    assert 'WindowStaysOnTopHint' not in init


def test_common_topmost_only_inherits_from_owner_and_focus_return_is_conditional():
    app = NS(activeWindow=Mock())
    env = load_functions('remote_confirmation.py', ['prepare_owned_dialog','hide_owned_dialog'],
                         {'Qt': NS(WindowType=NS(WindowStaysOnTopHint=8)), 'QApplication': app})
    owner = NS(windowFlags=Mock(return_value=8), isVisible=Mock(return_value=True), activateWindow=Mock())
    owner.window = lambda: owner
    dialog = NS(parentWidget=lambda: owner, setWindowFlag=Mock(), hide=Mock())
    env['prepare_owned_dialog'](dialog)
    dialog.setWindowFlag.assert_called_once_with(8, True)
    dialog.setWindowFlag.reset_mock()
    owner.windowFlags.return_value = 0
    env['prepare_owned_dialog'](dialog)
    dialog.setWindowFlag.assert_not_called()
    app.activeWindow.return_value = dialog
    env['hide_owned_dialog'](dialog)
    owner.activateWindow.assert_called_once_with()
    app.activeWindow.return_value = object()
    env['hide_owned_dialog'](dialog)
    assert owner.activateWindow.call_count == 1
    assert dialog.hide.call_count == 2


def test_common_confirmation_owner_is_independent_of_input_routing():
    source = ast.unparse(method('remote_confirmation.py', 'RemoteConfirmation', '__init__'))
    assert 'self.launcher = launcher' in source
    assert 'QMessageBox(launcher if owner is None else owner.window())' in source
    for file, cls in [('remote_confirmation.py','RemoteConfirmation'),('remote_text_dialog.py','RemoteTextDialog')]:
        ask = ast.unparse(method(file, cls, 'ask'))
        assert 'prepare_owned_dialog(self.dialog)' in ask
        assert 'hide_owned_dialog(self.dialog)' in ask
        assert 'ConfirmationInputGuard(self.dialog, remote, self)' in ask
        assert 'application.installEventFilter(guard)' in ask
        assert 'application.removeEventFilter(guard)' in ask
        assert 'self.dialog.setModal(True)' not in ask


def test_qt_copy_and_confirmation_parent(command_inputs):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
    from commander.window import CommanderWindow
    from remote_confirmation import RemoteConfirmation
    app = QApplication.instance() or QApplication([])
    launcher = QWidget()
    launcher.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    launcher.show()
    script, definition, values = command_inputs
    window = CommanderWindow(launcher, script, definition, None)
    try:
        window.show()
        assert not window.copy_button.isEnabled()
        window.values.update(values)
        window.refresh_breadcrumbs()
        assert window.copy_button.isEnabled()
        window.copy_button.click()
        assert app.clipboard().text() == build_command(definition, values, script).powershell_text()
        assert window.process is None
        confirmation = RemoteConfirmation(launcher, 'test', 'test', owner=window)
        assert confirmation.dialog.parentWidget() is window
        assert confirmation.dialog.windowModality() == Qt.WindowModality.NonModal
        QTimer.singleShot(0, lambda: confirmation.dialog.button(QMessageBox.StandardButton.No).click())
        assert confirmation.ask() == QMessageBox.StandardButton.No
    finally:
        window.close()
        launcher.close()
