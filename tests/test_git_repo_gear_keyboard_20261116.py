"""Regression for the Settings QMenu arrows and two-stage Git commit wheel.

Runs actual source methods with Qt-free doubles; no Git commands or Windows UI.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

from test_shared_dialog_contract_20261112 import load_methods, FakeBox
from test_list_confirmation_click_gate_20261110 import setup_question, send_click, event

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'src/app.py').read_text('utf-8')
WHEEL = (ROOT / 'src/remote_context_wheel.py').read_text('utf-8')
TEXT = (ROOT / 'src/remote_text_dialog.py').read_text('utf-8')
GUARD = (ROOT / 'src/remote_confirmation.py').read_text('utf-8')


class Combo:
    def __init__(self):
        self.items = ['選択してください...', 'FRB', 'FRB Launch', 'JSON Studio']
        self.index = 0
        self.focus = Mock()
    def count(self): return len(self.items)
    def currentIndex(self): return self.index
    def setCurrentIndex(self, index): self.index = index
    def setFocus(self, reason): self.focus(reason)
    def currentText(self): return self.items[self.index]


def git_adapter():
    Dialog, Box = load_methods()
    buttons = FakeBox([('OK', 1, 10), ('Cancel', 2, 20)])
    selector = Combo()
    launcher = NS(remote_window=None)
    adapter = Dialog(launcher, NS(setDefaultButton=Mock()), selector, buttons,
                     selection_combo=selector)
    return adapter, selector, buttons.buttons()


def test_settings_menu_uses_the_existing_keyboard_remote_runner_for_every_open():
    # Tool menus do not reliably receive native QWidget focus on Windows.
    assert 'self.theme_menu._frb_keyboard_opened = True' in APP
    assert 'self._wire_hybrid_context_menu(self.theme_menu, context=False)' in APP
    assert 'self.open_theme_menu_at(self.theme_button)' in APP
    cls = next(n for n in ast.parse(WHEEL).body if isinstance(n, ast.ClassDef)
               and n.name == 'RemoteContextWheel')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == 'eventFilter')
    keys = NS(Key_Up=1, Key_Down=2, Key_Left=3, Key_Right=4,
              Key_Return=5, Key_Enter=6, Key_Escape=7)
    qt = NS(Key=keys, KeyboardModifier=NS(NoModifier=0))
    env = dict(Qt=qt, QEvent=NS(Type=NS(KeyPress=99)))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<remote wheel keyboard>', 'exec'), env)
    handler = env['eventFilter']
    menu = NS(_frb_keyboard_opened=True, isVisible=lambda: True)
    commands = []
    controller = NS(active=True, root=menu, command=lambda c: commands.append(c))
    for value in (1, 2, 3, 4, 5, 6, 7):
        ev = NS(type=lambda: 99, modifiers=lambda: 0, key=lambda n=value: n,
                accept=Mock())
        assert handler(controller, object(), ev)
        ev.accept.assert_called_once()
    assert commands == ['UP', 'DOWN', 'LEFT', 'RIGHT', 'ENTER', 'ENTER', 'ESCAPE']


def test_git_dialog_wheel_always_starts_at_repo_placeholder_and_wraps_real_entries():
    adapter, combo, buttons = git_adapter()
    ok, cancel = buttons
    assert adapter.input_mode == 'choice'
    assert adapter.background_click_enabled
    assert combo.currentIndex() == 0
    adapter.focus_combo()
    adapter.remote_command('DOWN')
    assert combo.currentIndex() == 1
    adapter.remote_command('DOWN')
    assert combo.currentIndex() == 2
    adapter.remote_command('UP')
    assert combo.currentIndex() == 1
    adapter.remote_command('UP')
    assert combo.currentIndex() == 3  # No wrap into 'select...'.
    assert combo.focus.call_count >= 4
    assert ok.click.call_count == 0 and cancel.click.call_count == 0


def test_git_unrelated_click_changes_wheel_target_not_the_commit_result():
    adapter, combo, buttons = git_adapter()
    ok, cancel = buttons
    adapter.remote_command('DOWN')
    assert combo.currentIndex() == 1
    assert adapter.background_click('dialog') is True
    assert adapter.input_mode == 'buttons'
    assert adapter.selected == 'Cancel'
    assert adapter.remote_has_selected is False  # Stage change is not a user choice.
    assert ok.click.call_count == 0 and cancel.click.call_count == 0
    adapter.remote_command('DOWN')
    assert adapter.selected == 'OK'
    assert adapter.background_click('launch') is False  # Armed: guard dispatches CLICK.
    assert adapter.selected == 'OK'  # The second click must not reset to Cancel.
    assert ok.click.call_count == 0 and cancel.click.call_count == 0
    adapter.focus_combo()  # Native selector click restores first stage.
    assert adapter.input_mode == 'choice'
    adapter.remote_command('ENTER')  # Remote center does not skip verification.
    assert adapter.input_mode == 'buttons'
    assert ok.click.call_count == 0 and cancel.click.call_count == 0
    adapter.remote_command('RIGHT')
    adapter.remote_command('CLICK')
    ok.click.assert_called_once()


def test_actual_app_input_guard_uses_unrelated_click_only_for_focus_switch():
    module, guard, original, buttons, pad, viewport, view, remote = setup_question()
    adapter, combo, dialog_buttons = git_adapter()
    adapter.launcher = original.launcher
    adapter.launcher.remote_window.isVisible = lambda: False
    guard.wheel_receiver = adapter
    assert guard.eventFilter(viewport, event(module.QEvent.Type.Wheel))
    assert combo.currentIndex() == 1  # Background wheel -> repository.
    send_click(module, guard, viewport)
    assert adapter.input_mode == 'buttons'
    assert all(b.click.call_count == 0 for b in dialog_buttons)
    assert guard.eventFilter(viewport, event(module.QEvent.Type.Wheel))
    assert adapter.selected == 'OK'
    send_click(module, guard, viewport)  # Explicit wheel selection + next click commits.
    dialog_buttons[0].click.assert_called_once()
    dialog_buttons[1].click.assert_not_called()


def test_git_uses_shared_dialog_contract_and_native_editing():
    assert 'wheel_combo=repository_selector' in APP
    assert 'selection_combo=wheel_combo' in APP
    assert 'self.dialog.setModal(False)' in TEXT
    assert 'self.editor.setFocus' in TEXT
    assert 'self.focus_combo()' in TEXT
    assert 'receiver.background_click_enabled' in GUARD or "'background_click_enabled'" in GUARD
    assert 'self._native_dialog_control(obj)' in GUARD
