"""Shared terminal-selection boundary. Never closes unrelated windows.

Navigation (submenu, preview opener, filter widgets) is not a command.
Closing a menu does not depend on the outcome or duration of its command.
"""
from processing_display import processing_display


def is_terminal(menu, action):
    if action is None or not action.isEnabled() or not action.isVisible():
        return False
    if action.isSeparator() or action.menu() is not None:
        return False
    if action in getattr(menu, 'openers', {}) or action in getattr(menu, '_branch_actions', ()):
        return False
    if action is getattr(menu, 'folder_list_action', None):
        return False
    # QWidgetAction search and scroll containers are not commands.
    if callable(getattr(action, 'defaultWidget', None)) and action.defaultWidget() is not None:
        return False
    return True


def owned_children(menu):
    children = [getattr(menu, 'child', None)]
    for name in ('_submenus', '_context_menus'):
        children.extend(getattr(menu, name, {}).values())
    for action in getattr(menu, 'actions', lambda: ())():
        try:
            children.append(action.menu())
        except RuntimeError:
            pass
    return [child for child in children if child is not None]


def selection_root(menu):
    """Follow explicit cascade ownership, never an arbitrary QWidget parent."""
    seen = set()
    while menu is not None and id(menu) not in seen:
        seen.add(id(menu))
        parent = getattr(menu, 'parentWidget', lambda: None)()
        if parent is None or getattr(parent, 'child', None) is not menu:
            return menu
        menu = parent
    return menu


def close_menu_tree(root, *, include_root=True):
    """Traverse even hidden ancestors: independent Tool descendants may remain."""
    seen = set()
    def visit(menu, close):
        if menu is None or id(menu) in seen:
            return
        seen.add(id(menu))
        try:
            for child in owned_children(menu):
                visit(child, True)
            if close and menu.isVisible():
                menu.close()
        except RuntimeError:  # already disposed Qt wrapper
            pass
    visit(root, include_root)


def close_selection(root, action=None):
    """Close a command popup and its explicitly linked selection session.

    A handoff to an inline editor may retain its hosting column; the action
    popup itself always closes. Arbitrary QWidget parents are never closed.
    """
    parent = getattr(root, '_frb_selection_parent', None)
    retain_host = bool(action is not None and callable(getattr(action, 'property', None))
                       and action.property('frb_handoff_to_selection_host'))
    close_menu_tree(root)
    if parent is not None and not retain_host:
        close_menu_tree(parent)


def finish_selection(root, callback, *, defer=None, after_close=None, action=None):
    """Close only this selection session, then dispatch exactly once.

    A session guard is reset by its next aboutToShow (persistent menus).
    The handoff hook preserves the Keyboard Ex foreground timing contract.
    """
    if getattr(root, '_frb_terminal_dispatched', False):
        return False
    root._frb_terminal_dispatched = True
    close_selection(root, action)
    if after_close is not None:
        after_close()
    def run():
        return processing_display().run(callback)
    if defer is None:
        run()
    else:
        defer(run)
    return True


def close_after_native_trigger(root, action):
    """Fallback for native/programmatic QAction activation, scoped to its root."""
    if root.isVisible() and is_terminal(root, action):
        close_selection(root, action)


def reset_selection(root):
    root._frb_terminal_dispatched = False


def install_terminal_menu(root):
    """Attach once to an action QMenu (including late-created submenus).

    Intercept terminal activation *before* QAction callbacks. A triggered
    signal alone is too late if a callback opens a nested modal dialog.
    Native submenu/navigation handling remains Qt's responsibility.
    """
    if getattr(root, '_frb_terminal_filter', None) is not None:
        return
    from PySide6.QtCore import QObject, QEvent, Qt
    from PySide6.QtWidgets import QMenu

    class TerminalFilter(QObject):
        def __init__(self):
            super().__init__(root)
            self.press = None
            root.aboutToShow.connect(self.prepare)
            root.aboutToHide.connect(self.cleanup)
            root.triggered.connect(self.on_triggered)
            self.attach(root)

        def attach(self, menu):
            if getattr(menu, '_frb_terminal_owner', None) is self:
                return
            menu._frb_terminal_owner = self
            if menu is not root and getattr(root, '_frb_non_grabbing', False):
                menu.setWindowFlags(root.windowFlags())
            menu.installEventFilter(self)
            for action in menu.actions():
                child = action.menu()
                if isinstance(child, QMenu):
                    self.attach(child)

        def prepare(self):
            reset_selection(root)
            self.press = None
            for action in root.actions():
                child = action.menu()
                if isinstance(child, QMenu):
                    self.attach(child)

        def on_triggered(self, action):
            # Fallback for QAction shortcuts/programmatic activations not
            # originating from a mouse release or Enter. Never close previews.
            close_after_native_trigger(root, action)

        def cleanup(self):
            self.press = None
            close_menu_tree(root, include_root=False)

        def eventFilter(self, menu, event):
            kind = event.type()
            if kind == QEvent.Type.ActionAdded or kind == QEvent.Type.Show:
                for action in menu.actions():
                    child = action.menu()
                    if isinstance(child, QMenu):
                        self.attach(child)
                return False
            if not root.isVisible():
                return False
            action = None
            if kind == QEvent.Type.MouseButtonPress:
                self.press = (menu, menu.actionAt(event.position().toPoint())) if event.button() == Qt.MouseButton.LeftButton else None
                return False
            if kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                action = menu.actionAt(event.position().toPoint())
                pressed = self.press
                self.press = None
                if pressed != (menu, action):
                    return False
            elif kind == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() == Qt.KeyboardModifier.NoModifier:
                action = menu.activeAction()
            else:
                return False
            if not is_terminal(menu, action):
                return False
            event.accept()
            finish_selection(root, action.trigger, action=action)
            return True

    root._frb_terminal_filter = TerminalFilter()
