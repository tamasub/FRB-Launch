"""2026-11-18: Exp right-click must hand keyboard arrows to the open menu.

No GUI available on CI: drive the production FRBContextMenu factory and the
production RemoteContextWheel event filter with Qt-free test doubles.
"""
from types import SimpleNamespace as NS

from test_frb_context_menu_owns_runner_20261112 import harness as context_menu_harness
from test_remote_context_wheel_prototype_20261103 import (
    FakeAction, harness as wheel_harness,
)


def test_exp_and_list_pointer_context_menus_enable_keyboard_navigation():
    menus = context_menu_harness()
    exp = menus.factory(menus.launcher)
    files_list = menus.factory(menus.launcher)
    assert exp._frb_keyboard_opened is True
    assert files_list._frb_keyboard_opened is True
    # Each actual menu still installs its one existing controller, not a
    # new Exp-specific shortcut or a keyboard focus transfer.
    exp.popup()
    while menus.pending:
        menus.pending.pop(0)()
    assert exp._frb_grigri_runner.active
    exp.close()
    assert not exp._frb_grigri_runner


def test_exp_focus_does_not_steal_arrows_enter_or_escape_while_menu_visible(wheel_harness):
    mod = wheel_harness.module
    mod.QEvent.Type.KeyPress = 'keyboard'
    mod.Qt.KeyboardModifier = NS(NoModifier=0)
    mod.Qt.Key = NS(Key_Up=1, Key_Down=2, Key_Left=3, Key_Right=4,
                    Key_Return=5, Key_Enter=6, Key_Escape=7)

    class KeyEvent:
        def __init__(self, key):
            self.pressed = key
            self.accepted = False
        def type(self): return 'keyboard'
        def key(self): return self.pressed
        def modifiers(self): return 0
        def accept(self): self.accepted = True

    # QTreeView remains the keyboard-focus owner in the real non-grabbing Tool
    # popup. The application-wide runner intercepts it *before* Exp changes
    # its current index or Enter opens a folder.
    exp_tree = NS(objectName=lambda: 'filesExpTree')
    copy = FakeAction('コピー')
    delete = FakeAction('削除')
    menu, runner = wheel_harness.new_menu(copy, delete)
    menu._frb_keyboard_opened = True
    wheel_harness.drain()
    assert runner in wheel_harness.app.filters
    assert menu.activeAction() is copy

    for key in (2, 1, 2):  # Down / Up / Down
        event = KeyEvent(key)
        assert runner.eventFilter(exp_tree, event) is True
        assert event.accepted
    assert menu.activeAction() is delete
    assert copy.trigger_calls == delete.trigger_calls == 0

    event = KeyEvent(5)  # Enter executes highlighted QAction once.
    assert runner.eventFilter(exp_tree, event) is True
    assert event.accepted
    assert not menu.isVisible()
    wheel_harness.drain()
    assert delete.trigger_calls == 1
    assert copy.trigger_calls == 0
    assert runner not in wheel_harness.app.filters
    assert runner.eventFilter(exp_tree, KeyEvent(2)) is False

    # Escape dismisses without executing any command.
    second, second_runner = wheel_harness.new_menu(FakeAction('貼り付け'))
    second._frb_keyboard_opened = True
    wheel_harness.drain()
    event = KeyEvent(7)
    assert second_runner.eventFilter(exp_tree, event) is True
    assert not second.isVisible()
    assert second.actions()[0].trigger_calls == 0
    assert second_runner not in wheel_harness.app.filters
