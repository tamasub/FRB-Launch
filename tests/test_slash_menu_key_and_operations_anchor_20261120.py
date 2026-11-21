"""Regressions: physical Menu key reuses Right and operations appear by caption."""
from pathlib import Path
from types import SimpleNamespace

from test_slash_exp_navigation_20261118 import (
    Event, FakeQMenu, Item, Panel, make_launcher, nav,
)

ROOT = Path(__file__).resolve().parents[1]


def _leaf_context(nav, key_code):
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
    event = Event(key_code)
    menu.keyPressEvent(event)
    child = menu.activeAction().menu()
    assert child is not None and child.isVisible()
    assert child._context_source is source  # Reuses EXISTING Copy/Paste QAction source.
    assert calls == []  # Opening a menu must not commit a folder / mutate current.
    return mod, menu, child, event


def test_physical_menu_key_uses_same_operations_as_right(nav):
    mod, key = nav
    key.Key_Menu = 108
    _, right_menu, right_child, _ = _leaf_context(nav, key.Key_Right)
    _, menu_key_menu, menu_key_child, physical = _leaf_context(nav, key.Key_Menu)
    assert physical.isAccepted()  # No native Qt ContextMenu fallback.
    assert right_child._full_text.keys() == menu_key_child._full_text.keys() or (
        [a.text() for a in right_child._action_items] ==
        [a.text() for a in menu_key_child._action_items])
    assert right_menu.isVisible() and menu_key_menu.isVisible()


def test_menu_key_on_branch_does_not_jump_back_to_exp(nav):
    mod, key = nav
    key.Key_Menu = 108
    child = Item('child', {'virtual': {'kind': 'file', 'node_id': 'child', 'row': {}}})
    folder = Item('folder', {'virtual': {'kind': 'folder', 'node_id': 'parent'}}, child)
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([folder]))
    menu.populate()
    menu.popup((10, 10))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Menu))
    assert menu.activeAction().menu().isVisible()  # Same as Right on a branch.
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


def test_list_menu_key_and_native_context_event_share_existing_right_handler():
    app = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    view = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    start = app.index('    def expanded_tree_key(')
    end = app.index('    def wheel_classic_menu(', start)
    route = app[start:end]
    assert "event.key() == getattr(Qt.Key, 'Key_Menu', None)" in route
    assert 'key = (Qt.Key.Key_Right if pane is self.expanded_view.middle' in route
    assert 'view.context_menu(pane, point, global_pos=position)' in route
    start = view.rindex('    def eventFilter(self, obj, event):')
    event_route = view[start:start + 1400]
    assert 'QContextMenuEvent.Reason.Keyboard' in event_route
    assert 'self.launcher.expanded_tree_key(self.middle.tree, right)' in event_route


def test_actual_list_menu_key_and_right_use_same_context_and_near_name(nav):
    """Execute production Launcher.expanded_tree_key with a focused List fake."""
    from test_expanded_keyboard_dispatch_20261024 import instance, Qt
    mod, _ = nav
    Qt.Key.Key_Menu = 111
    launcher = instance()
    view = launcher.expanded_view
    tree = view.middle.tree
    item = tree.currentItem()
    item.text = lambda col: 'src'
    class Rect:
        def center(self): return mod.QPoint(160, 15)
        def left(self): return 0
        def right(self): return 400
    tree.visualItemRect = lambda _: Rect()
    tree.header = lambda: SimpleNamespace(sectionViewportPosition=lambda i: 0,
                                          sectionSize=lambda i: 260)
    tree.fontMetrics = lambda: SimpleNamespace(horizontalAdvance=lambda name: len(name) * 7)
    tree.viewport = lambda: SimpleNamespace(mapToGlobal=lambda point: point)
    recorded = []
    view.context_menu = lambda pane, point, *, global_pos: recorded.append(
        (pane, point.x(), point.y(), global_pos.x()))
    launcher._launch_context_menu = SimpleNamespace(isVisible=lambda: True)
    ns = launcher.expanded_tree_key.__func__.__globals__
    ns.update(QPoint=mod.QPoint, _row_text_anchor_local_x=mod._row_text_anchor_local_x)
    class KeyEvent:
        def __init__(self, k): self.k = k; self.accepted = False
        def key(self): return self.k
        def modifiers(self): return 0
        def accept(self): self.accepted = True
    right = KeyEvent(Qt.Key.Key_Right)
    physical = KeyEvent(Qt.Key.Key_Menu)
    assert launcher.expanded_tree_key(tree, right)
    assert launcher.expanded_tree_key(tree, physical)
    assert right.accepted and physical.accepted
    assert recorded[0] == recorded[1]
    assert recorded[0][1] == 8 + 24 + 3 * 7 + 28  # not the full-row center
    assert launcher._launch_context_menu._frb_keyboard_opened is True
    assert view.actions == []  # No Exp/selection mutation.


def test_native_keyboard_context_event_routes_to_right_not_qt_default(nav, monkeypatch):
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
    menu.setActiveAction(next(iter(menu._action_items)))
    class KeyboardContext:
        accepted = False
        def type(self): return 707
        def reason(self): return 9
        def accept(self): self.accepted = True
    event = KeyboardContext()
    assert menu.event(event)
    assert event.accepted
    assert menu.activeAction().menu()._context_source is source
    assert calls == []
