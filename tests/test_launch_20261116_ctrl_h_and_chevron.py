"""Ctrl+H Files List history keys and compact Launch Menu arrow (Qt-independent)."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SRC = Path(__file__).resolve().parents[1] / 'src'


def source_of(filename, klass, name):
    content = (SRC / filename).read_text(encoding='utf-8')
    module = ast.parse(content)
    target = next(x for x in module.body if isinstance(x, ast.ClassDef) and x.name == klass)
    node = next(x for x in target.body if isinstance(x, ast.FunctionDef) and x.name == name)
    return ast.get_source_segment(content, node)


def execute_method(filename, klass, name, globs):
    source = source_of(filename, klass, name)
    namespace = dict(globs)
    exec(compile(source, str(SRC / filename), 'exec'), namespace)
    return namespace[name]


class Key:
    Key_Down = 1
    Key_Up = 2
    Key_Return = 3
    Key_Enter = 4
    Key_Escape = 5
    Key_G = 6
    Key_H = 7


class FocusReason:
    ShortcutFocusReason = 1


class Qt:
    Key = Key
    KeyboardModifier = NS(NoModifier=0, ControlModifier=1)
    FocusReason = FocusReason


class Event:
    def __init__(self, key):
        self._key = key
        self.accepted = False

    def type(self):
        return 10

    def modifiers(self):
        return 0

    def key(self):
        return self._key

    def accept(self):
        self.accepted = True


class FakeAction:
    def __init__(self):
        self.trigger_count = 0

    def trigger(self):
        self.trigger_count += 1


class FakeMenu:
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


class FakeButton:
    def __init__(self):
        self.focus_calls = []

    def setFocus(self, reason):
        self.focus_calls.append(reason)


def test_ctrl_h_focus_targets_local_search_without_changing_other_histories():
    expanded = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    launcher = (SRC / 'app.py').read_text(encoding='utf-8')
    assert 'event.key() == Qt.Key.Key_H' in expanded
    assert 'k == Qt.Key.Key_H' in launcher
    assert 'self.expanded_view.focus_middle_search_history()' in launcher
    assert "self._workspace_mode == 'files'" in expanded
    assert 'self.middle_search_history_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)' in expanded
    assert 'self.middle_search_history_menu.installEventFilter(self)' in expanded
    focus = execute_method('expanded_view.py', 'ExpandedLauncherView',
                           'focus_middle_search_history', {'Qt': Qt})
    button = FakeButton()
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              middle_search_history_button=button)
    assert focus(view) is True
    assert button.focus_calls == [FocusReason.ShortcutFocusReason]
    view._workspace_mode = 'other'
    assert focus(view) is False
    assert len(button.focus_calls) == 1


def test_down_opens_then_navigates_saved_search_keywords_enter_applies():
    navigate = execute_method('expanded_view.py', 'ExpandedLauncherView',
                              'handle_middle_search_history_key',
                              {'QEvent': NS(Type=NS(KeyPress=10)), 'Qt': Qt})
    menu, button, first, second = FakeMenu(), FakeButton(), FakeAction(), FakeAction()
    def toggle():
        menu.visible = not menu.visible
    view = NS(middle_search_history_button=button,
              middle_search_history_menu=menu,
              _middle_search_history_keyword_actions=[first, second],
              toggle_middle_search_history_menu=toggle)
    assert navigate(view, button, Event(Key.Key_Down)) is True
    assert menu.visible and menu.active is None, 'First Down only opens history'
    assert navigate(view, menu, Event(Key.Key_Down)) is True
    assert menu.active is first
    assert navigate(view, menu, Event(Key.Key_Down)) is True
    assert menu.active is second
    assert navigate(view, menu, Event(Key.Key_Down)) is True
    assert menu.active is first, 'Selection wraps like other history lists'
    assert navigate(view, menu, Event(Key.Key_Up)) is True
    assert menu.active is second
    enter = Event(Key.Key_Return)
    assert navigate(view, menu, enter) is True
    assert enter.accepted and second.trigger_count == 1 and not menu.visible


def test_escape_returns_focus_and_empty_history_is_safe():
    navigate = execute_method('expanded_view.py', 'ExpandedLauncherView',
                              'handle_middle_search_history_key',
                              {'QEvent': NS(Type=NS(KeyPress=10)), 'Qt': Qt})
    menu, button = FakeMenu(), FakeButton()
    view = NS(middle_search_history_button=button,
              middle_search_history_menu=menu,
              _middle_search_history_keyword_actions=[],
              toggle_middle_search_history_menu=lambda: setattr(menu, 'visible', True))
    assert navigate(view, button, Event(Key.Key_Down)) is True
    assert navigate(view, menu, Event(Key.Key_Down)) is True
    assert navigate(view, menu, Event(Key.Key_Enter)) is True
    esc = Event(Key.Key_Escape)
    assert navigate(view, menu, esc) is True
    assert esc.accepted and not menu.visible
    assert button.focus_calls == [FocusReason.ShortcutFocusReason]


def test_launch_submenu_chevron_uses_existing_compact_painter():
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    painter = source_of('app.py', 'RemoteFolderActionsMenu', '_paint_action_chevrons')
    assert "menu.launch_submenu_action = launch_sub.menuAction()" in app
    assert "getattr(self, 'launch_submenu_action', None)" in painter
    assert "getattr(self, 'new_submenu_action', None)" in painter
    assert 'self.contentsRect().right() - 13' in painter
    assert 'arrow.moveTo(cx - 2, cy - 4)' in painter
    assert 'arrow.lineTo(cx - 2, cy + 4)' in painter
    assert 'painter.fillRect(' in painter  # mask native larger glyph
