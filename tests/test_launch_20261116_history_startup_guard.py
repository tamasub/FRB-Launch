"""Regression: Qt eventFilter may fire before Files List history QMenu exists.

No PySide6 needed. These are executable copies of the real class methods,
extracted from AST; not hand-written substitutes for the implementation.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py'


def method(name, globals_):
    raw = SOURCE.read_text(encoding='utf-8')
    tree = ast.parse(raw)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'ExpandedLauncherView')
    function = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                    and node.name == name)
    namespace = dict(globals_)
    exec(compile(ast.get_source_segment(raw, function), str(SOURCE), 'exec'), namespace)
    return namespace[name]


class Key:
    Key_Down = 1
    Key_Return = 2
    Key_H = 3
    Key_Up = 4
    Key_Enter = 5
    Key_Escape = 6


class Qt:
    Key = Key
    KeyboardModifier = NS(NoModifier=0, ControlModifier=1)
    FocusReason = NS(ShortcutFocusReason=4)


QEvent = NS(Type=NS(KeyPress=10))


class KeyEvent:
    def __init__(self, key, modifiers=0):
        self._key = key
        self._modifiers = modifiers
        self.accepted = False

    def type(self):
        return QEvent.Type.KeyPress

    def modifiers(self):
        return self._modifiers

    def key(self):
        return self._key

    def accept(self):
        self.accepted = True


class Button:
    def __init__(self):
        self.focus_log = []

    def setFocus(self, reason):
        self.focus_log.append(reason)


class Menu:
    def __init__(self):
        self.visible = False
        self.active = None

    def isVisible(self):
        return self.visible

    def setActiveAction(self, action):
        self.active = action

    def activeAction(self):
        return self.active

    def hide(self):
        self.visible = False


def test_history_handler_is_safe_before_button_is_created():
    handler = method('handle_middle_search_history_key', {'QEvent': QEvent, 'Qt': Qt})
    view = NS()  # global filter may run early in __init__
    assert handler(view, object(), KeyEvent(Key.Key_Down)) is False


def test_history_handler_is_safe_between_button_and_menu_creation():
    handler = method('handle_middle_search_history_key', {'QEvent': QEvent, 'Qt': Qt})
    button = Button()
    view = NS(middle_search_history_button=button)
    assert handler(view, button, KeyEvent(Key.Key_Down)) is False
    assert handler(view, button, KeyEvent(Key.Key_Return)) is False
    assert handler(view, button, KeyEvent(Key.Key_Down, modifiers=1)) is False
    assert handler(view, object(), KeyEvent(Key.Key_Down)) is False
    # Also handle an explicit None sentinel for the in-progress menu.
    view.middle_search_history_menu = None
    assert handler(view, button, KeyEvent(Key.Key_Down)) is False


def test_ctrl_h_focus_is_safe_during_partial_initialization():
    focus = method('focus_middle_search_history', {'Qt': Qt})
    button = Button()
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              middle_search_history_button=button)
    assert focus(view) is False
    assert button.focus_log == []
    view.middle_search_history_menu = Menu()
    assert focus(view) is True
    assert button.focus_log == [Qt.FocusReason.ShortcutFocusReason]


def test_ready_history_still_opens_and_navigates_with_down():
    handler = method('handle_middle_search_history_key', {'QEvent': QEvent, 'Qt': Qt})
    button = Button()
    menu = Menu()
    action = object()
    view = NS(middle_search_history_button=button,
              middle_search_history_menu=menu,
              _middle_search_history_keyword_actions=[action],
              toggle_middle_search_history_menu=lambda: setattr(menu, 'visible', True))
    assert handler(view, button, KeyEvent(Key.Key_Down)) is True
    assert menu.visible is True
    assert menu.active is None
    assert handler(view, menu, KeyEvent(Key.Key_Down)) is True
    assert menu.active is action


def test_application_filter_guards_menu_before_calling_adapter():
    raw = SOURCE.read_text(encoding='utf-8')
    code = ast.get_source_segment(
        raw,
        next(node for cls in ast.parse(raw).body
             if isinstance(cls, ast.ClassDef) and cls.name == 'ExpandedLauncherView'
             for node in cls.body
             if isinstance(node, ast.FunctionDef) and node.name == 'eventFilter')
    )
    assert "getattr(self, 'middle_search_history_menu', None) is not None" in code
    assert 'self.handle_middle_search_history_key(obj, event)' in code
