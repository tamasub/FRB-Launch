"""Regression: Ctrl+G breadcrumb history arrows work even when the native Tool
window never activates (Windows WA_ShowWithoutActivating). No Qt dependency.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SOURCE = (Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py').read_text('utf-8')


def load(name, namespace):
    tree = ast.parse(SOURCE)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ExpandedLauncherView')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'expanded_view.py', 'exec'), namespace)
    return namespace[name]


class Key:
    Key_Up = 1
    Key_Down = 2
    Key_Return = 3
    Key_Enter = 4
    Key_Right = 5
    Key_Delete = 6
    Key_Escape = 7
    Key_Left = 8


Qt = NS(Key=Key, KeyboardModifier=NS(NoModifier=0), FocusReason=NS(ShortcutFocusReason=100))
QEvent = NS(Type=NS(KeyPress=9))


class Widget:
    def __init__(self):
        self.reasons = []
    def setFocus(self, reason):
        self.reasons.append(reason)


class Event:
    def __init__(self, key, mods=0):
        self._key, self._mods, self.accepted = key, mods, False
    def key(self): return self._key
    def modifiers(self): return self._mods
    def type(self): return 9
    def accept(self): self.accepted = True


class Tree:
    def __init__(self): self.rows = ['A', 'B', 'C']; self.selected = 'A'
    def currentItem(self): return self.selected
    def topLevelItemCount(self): return len(self.rows)
    def topLevelItem(self, index): return self.rows[index]
    def setCurrentItem(self, item): self.selected = item
    def scrollToItem(self, item): pass


def move(tree, direction):
    i = tree.rows.index(tree.selected)
    tree.selected = tree.rows[(i + direction) % len(tree.rows)]


NAMESPACE = dict(Qt=Qt, QEvent=QEvent, QApplication=NS(activeModalWidget=lambda: None),
                 move_tree_selection=move)


def setup():
    func = load('handle_directory_favorites_key', NAMESPACE.copy())
    tree = Tree()
    popup = NS(visible=True, isVisible=lambda: popup.visible)
    ops = []
    panel = NS(isVisible=lambda: True, _workspace_mode='files', favorite_popup=popup,
               favorite_choices=tree, _launch_owns_keyboard_source=lambda obj: obj != 'external',
               hide_favorite_popup=lambda: (ops.append('hide'), setattr(popup, 'visible', False)),
               middle='list-panel', focus_panel=lambda obj: ops.append(('focus', obj)),
               directory_favorite_clicked=lambda row, col: ops.append(('navigate', row, col)))
    return func, panel, tree, popup, ops


def test_up_down_enter_arriving_on_owner_routes_to_breadcrumb_not_list():
    fn, view, tree, popup, ops = setup()
    for key, expected in [(Key.Key_Down, 'B'), (Key.Key_Down, 'C'),
                          (Key.Key_Up, 'B')]:
        event = Event(key)
        assert fn(view, 'list-widget', event) is True
        assert event.accepted and tree.selected == expected
    event = Event(Key.Key_Enter)
    assert fn(view, 'breadcrumb-button', event)
    assert ops == [('navigate', 'B', 0)]


def test_escape_returns_focus_to_list_and_consumes_event():
    fn, view, tree, popup, ops = setup()
    event = Event(Key.Key_Escape)
    assert fn(view, 'breadcrumb-button', event)
    assert not popup.visible and ops == ['hide', ('focus', 'list-panel')]


def test_keyboard_modal_and_foreign_widgets_are_not_hijacked():
    fn, view, tree, popup, ops = setup()
    for source, modifier in [('external', 0), ('list-widget', 2)]:
        event = Event(Key.Key_Down, modifier)
        assert fn(view, source, event) is False
        assert not event.accepted and tree.selected == 'A'
    event = Event(Key.Key_Left)
    assert fn(view, 'list-widget', event) is False
    popup.visible = False
    event = Event(Key.Key_Down)
    assert fn(view, 'list-widget', event) is False


def test_popup_keeps_real_focus_in_launcher_while_handling_keys():
    show = load('show_directory_favorites', dict(Qt=Qt))
    toggle = load('toggle_directory_favorites', dict(Qt=Qt))
    popup = NS(visible=False, isVisible=lambda:popup.visible, show=lambda:setattr(popup,'visible',True),
               raise_=lambda:None)
    button, choices = Widget(), Widget()
    view = NS(isVisible=lambda:True, _workspace_mode='files', favorite_popup=popup,
              favorite_dropdown=button, favorite_choices=choices,
              middle_search_history_menu=NS(isVisible=lambda:False),
              folder_favorites=NS(paths=['A']), launcher=NS(history_popup=NS(isVisible=lambda:False)),
              populate_directory_favorites=lambda:None, position_directory_favorites=lambda:None,
              refresh_guest_popup_priority=lambda:None,
              toggle_directory_favorites=lambda:toggle(view))
    assert show(view) is True
    assert button.reasons and choices.reasons == []
    assert button.reasons[-1] == Qt.FocusReason.ShortcutFocusReason
