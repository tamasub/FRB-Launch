"""Regressions: Right retains operation popup; Windows Menu key is inert.

2026-11-21: replaces the old physical-Menu-key-as-Right requirement. Keep
caption/positioning tests from the previous implementation.
"""
from pathlib import Path
from types import SimpleNamespace

from test_slash_exp_navigation_20261118 import (
    Event, FakeQMenu, Item, Panel, make_launcher, nav,
)

ROOT = Path(__file__).resolve().parents[1]


def _leaf_menu(nav):
    mod, key = nav
    launcher, calls = make_launcher()
    source = FakeQMenu()
    source.addAction('コピー')
    launcher.show_virtual_launch_context = lambda *args, **kwargs: source
    leaf = Item('file.txt', {'virtual': {'kind': 'file', 'node_id': 'file', 'row': {}}})
    menu = mod.SlashExpMenu(launcher, Panel([leaf]))
    menu.populate()
    menu.popup((10, 10))
    action = next(iter(menu._action_items))
    menu.setActiveAction(action)
    return mod, key, menu, action, calls


def test_right_still_opens_operations_menu_but_physical_menu_key_does_nothing(nav):
    mod, key, right_menu, _, calls = _leaf_menu(nav)
    right_menu.keyPressEvent(Event(key.Key_Right))
    child = right_menu.activeAction().menu()
    assert child is not None and child.isVisible()
    assert child._context_source is not None
    assert calls == []

    key.Key_Menu = 108
    _, _, physical_menu, action, physical_calls = _leaf_menu(nav)
    event = Event(key.Key_Menu)
    physical_menu.keyPressEvent(event)
    assert event.isAccepted()
    assert physical_menu.activeAction() is action
    assert action.menu() is None
    assert physical_menu._context_menus == {}
    assert physical_calls == []


def test_menu_key_on_branch_does_not_expand_or_go_back(nav):
    mod, key = nav
    key.Key_Menu = 108
    child = Item('child', {'virtual': {'kind': 'file', 'node_id': 'child', 'row': {}}})
    folder = Item('folder', {'virtual': {'kind': 'folder', 'node_id': 'parent'}}, child)
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([folder]))
    menu.populate()
    menu.popup((10, 10))
    action = next(iter(menu._action_items))
    menu.setActiveAction(action)
    physical = Event(key.Key_Menu)
    menu.keyPressEvent(physical)
    assert physical.isAccepted()
    assert action.menu() is None
    assert calls == []


def test_menu_key_does_not_interrupt_ime(nav):
    mod, key = nav
    key.Key_Menu = 108
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([Item('a', {'file': True})]))
    menu.populate()
    menu._search_edit.ime_composing = True
    event = Event(key.Key_Menu)
    menu.keyPressEvent(event)
    assert event.isAccepted()
    assert menu._context_menus == {}


def test_short_and_long_captions_move_operation_popup_horizontally(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([]))
    short = SimpleNamespace(text=lambda: 'abc')
    long = SimpleNamespace(text=lambda: 'filename_is_much_longer.md')
    assert menu._operation_popup_x(short) < menu._operation_popup_x(long)
    assert menu._operation_popup_x(long) <= menu.width() - 1


def test_fixed_scroll_caption_uses_same_offset_policy(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([]))
    action = object()
    menu._scroll_items[action] = SimpleNamespace(text=lambda col: 'abc')
    menu._scroll_tree = SimpleNamespace(
        viewport=lambda: SimpleNamespace(mapToGlobal=lambda pt: pt),
        fontMetrics=menu.fontMetrics)
    assert menu._operation_popup_x(action) == 29 + 3 * 7 + 28


def test_list_menu_key_has_no_right_alias_and_insert_uses_tonton():
    app = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    view = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    start = app.index('    def expanded_tree_key(')
    end = app.index('    def wheel_classic_menu(', start)
    route = app[start:end]
    assert "if event.key() == getattr(Qt.Key, 'Key_Menu', None):" in route
    assert "key == getattr(Qt.Key, 'Key_Insert', None)" in route
    assert 'self.expanded_view.clear_middle_row_for_folder_operation(' in route
    assert 'view.show_list_background_context(position)' in route
    assert 'view.context_menu(pane, point, global_pos=position)' in route
    assert 'key = (Qt.Key.Key_Right if pane is self.expanded_view.middle' not in route
    assert 'QContextMenuEvent.Reason.Keyboard' in view
    assert 'self.launcher.expanded_tree_key(self.middle.tree, right)' not in view


def test_actual_list_menu_key_no_op_and_right_on_folder_target():
    """Production Launcher.expanded_tree_key using existing Qt-free Dispatch."""
    from test_expanded_keyboard_dispatch_20261024 import instance, Qt
    Qt.Key.Key_Menu = 111
    launcher = instance()
    view = launcher.expanded_view
    tree = view.middle.tree
    called = []
    class KeyEvent:
        def __init__(self, k): self.k = k; self.accepted = False
        def key(self): return self.k
        def modifiers(self): return 0
        def accept(self): self.accepted = True
    physical = KeyEvent(Qt.Key.Key_Menu)
    assert launcher.expanded_tree_key(tree, physical)
    assert physical.accepted
    assert view.actions == []

    tree.deliberate_blank_selection = True
    lane = SimpleNamespace(
        rect=lambda: SimpleNamespace(center=lambda: 'lane-center'),
        mapToGlobal=lambda pos: ('current-folder-anchor', pos))
    view.middle_back_lane = lane
    view.show_list_background_context = lambda pos: called.append(pos)
    launcher._launch_context_menu = SimpleNamespace(isVisible=lambda: False)
    right = KeyEvent(Qt.Key.Key_Right)
    assert launcher.expanded_tree_key(tree, right)
    assert right.accepted
    assert called == [('current-folder-anchor', 'lane-center')]
    assert view.actions == []


def test_native_keyboard_context_event_no_longer_opens_slash_operations(nav, monkeypatch):
    import sys
    mod, key = nav
    mod.QEvent.Type.ContextMenu = 707
    qtgui = sys.modules['PySide6.QtGui']
    qtgui.QContextMenuEvent = SimpleNamespace(Reason=SimpleNamespace(Keyboard=9, Mouse=0))
    launcher, calls = make_launcher()
    source = FakeQMenu()
    source.addAction('コピー')
    launcher.show_virtual_launch_context = lambda *args, **kwargs: source
    leaf = Item('leaf', {'virtual': {'kind': 'file', 'node_id': 'leaf', 'row': {}}})
    menu = mod.SlashExpMenu(launcher, Panel([leaf]))
    menu.populate()
    menu.popup((10, 10))
    action = next(iter(menu._action_items))
    menu.setActiveAction(action)
    class KeyboardContext:
        accepted = False
        def type(self): return 707
        def reason(self): return 9
        def accept(self): self.accepted = True
    event = KeyboardContext()
    assert menu.event(event)
    assert event.accepted
    assert menu.activeAction() is action
    assert action.menu() is None
    assert calls == []
