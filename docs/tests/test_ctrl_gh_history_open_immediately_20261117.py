"""2026-11-17: Ctrl+G/H immediately show their separate history popups.

Run the production handlers without PySide6; keep the registered keyboard
navigation handlers and non-grabbing menus unchanged.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SRC = Path(__file__).resolve().parents[1] / 'src'


def method(filename, name):
    source = (SRC / filename).read_text('utf-8')
    module = ast.parse(source)
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef)
               and node.name == 'ExpandedLauncherView')
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name == name)
    namespace = {'Qt': NS(FocusReason=NS(ShortcutFocusReason=42))}
    exec(compile(ast.get_source_segment(source, node), filename, 'exec'), namespace)
    return namespace[name]


class Focusable:
    def __init__(self):
        self.reasons = []
    def setFocus(self, reason):
        self.reasons.append(reason)


class Popup:
    def __init__(self, visible=False):
        self.visible = visible
        self.hide_count = 0
        self.active = None
    def isVisible(self):
        return self.visible
    def hide(self):
        self.hide_count += 1
        self.visible = False
    def setActiveAction(self, action):
        self.active = action


def test_ctrl_g_shows_breadcrumb_favorites_and_focuses_arrow_tree():
    show = method('expanded_view.py', 'show_directory_favorites')
    popup, keyword_menu = Popup(), Popup(True)
    button, choices = Focusable(), Focusable()
    calls = []
    def toggle():
        calls.append('open')
        popup.visible = True
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              favorite_dropdown=button, favorite_popup=popup,
              favorite_choices=choices, middle_search_history_menu=keyword_menu,
              toggle_directory_favorites=toggle)
    assert show(view) is True
    assert calls == ['open']
    assert keyword_menu.hide_count == 1
    assert choices.reasons == [42]
    # Repeating Ctrl+G keeps the popup open, with its selection intact.
    assert show(view) is True
    assert calls == ['open']
    assert popup.isVisible()
    assert choices.reasons == [42, 42]
    assert button.reasons == [42]


def test_ctrl_h_shows_list_keyword_history_and_keeps_arrow_cursor():
    show = method('expanded_view.py', 'show_middle_search_history')
    menu, favorites = Popup(), Popup(True)
    button = Focusable()
    calls = []
    def focus():
        button.setFocus(42)
        return True
    def toggle():
        calls.append('open')
        menu.visible = True
        menu.active = 'register-command'
    view = NS(focus_middle_search_history=focus,
              middle_search_history_menu=menu,
              favorite_popup=favorites,
              hide_favorite_popup=favorites.hide,
              toggle_middle_search_history_menu=toggle)
    assert show(view) is True
    assert calls == ['open']
    assert favorites.hide_count == 1
    assert menu.active is None  # First Down selects a SAVED keyword.
    menu.active = 'selected keyword'
    assert show(view) is True
    assert menu.active == 'selected keyword', 'Repeat shortcut must not reset the cursor'
    assert calls == ['open']
    assert button.reasons == [42, 42]


def test_ctrl_h_does_not_open_before_button_initialized_or_outside_files():
    focus = method('expanded_view.py', 'focus_middle_search_history')
    show = method('expanded_view.py', 'show_middle_search_history')
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              middle_search_history_button=None, middle_search_history_menu=None,
              focus_middle_search_history=lambda: False)
    assert focus(view) is False
    assert show(view) is False
    view._workspace_mode = 'browser'
    assert focus(view) is False


def test_both_dispatchers_use_immediate_show_and_preserve_arrow_routes():
    app = (SRC / 'app.py').read_text('utf-8')
    view = (SRC / 'expanded_view.py').read_text('utf-8')
    assert 'self.expanded_view.show_directory_favorites()' in app
    assert 'self.expanded_view.show_middle_search_history()' in app
    assert 'self.show_directory_favorites()' in view
    assert 'self.show_middle_search_history()' in view
    assert 'move_tree_selection(self.favorite_choices,' in view
    assert 'self.directory_favorite_clicked(row, 0)' in view
    assert 'menu.setActiveAction(action)' in view
    assert 'action.trigger()  # Calls existing select_middle_search_history.' in view
    # The history controls remain part of the Files 6-stop Tab ring.
    assert "order = ('exp', 'list', 'folder_search', 'breadcrumb'," in view
