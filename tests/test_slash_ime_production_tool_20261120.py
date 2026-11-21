"""Portable regression tests for always-on activated Tool + click-away.

Native Windows IME composition was validated by the user with the A/B trace;
these tests protect the remaining menu and lifecycle contracts in CI.
"""
from types import SimpleNamespace

from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Item


def _open(nav):
    mod, key = nav
    launcher, calls = make_launcher()
    folder = Item('Folder', {'virtual': {'kind': 'folder', 'node_id': 'f',
                                      'children': [{'kind': 'file', 'title': 'leaf',
                                                    'node_id': 'leaf', 'row': {}}]}})
    assert mod.popup_exp_navigator(launcher, Panel([folder]), mod.QPoint(100, 100))
    return mod, key, launcher, calls, launcher._slash_exp_navigation_menu


def test_ime_tool_is_default_and_activated_without_debug_flag(nav, monkeypatch):
    monkeypatch.delenv('FRB_SLASH_IME_TOOL_WINDOW', raising=False)
    mod, key, launcher, calls, root = _open(nav)
    assert root.window_flags == (mod.Qt.WindowType.Tool |
                                 mod.Qt.WindowType.FramelessWindowHint |
                                 mod.Qt.WindowType.WindowStaysOnTopHint)
    assert root.activated
    # / remains an actual toggle, not a literal editor character.
    from test_slash_exp_navigation_20261118 import Event
    root.keyPressEvent(Event(key.Key_Slash, text='/'))
    assert not root.isVisible()


def test_click_inside_tool_keeps_session_click_outside_closes(nav):
    mod, _, launcher, _, root = _open(nav)
    application = mod.QApplication.instance()
    assert len(application.filters) == 1
    guard = application.filters[0]
    event = SimpleNamespace(type=lambda: mod.QEvent.Type.MouseButtonPress)
    # A search child belongs to the floating menu and must not dismiss it.
    child = mod.QWidget(root)
    child.parentWidget = lambda: root
    assert not guard.eventFilter(child, event)
    assert root.isVisible()
    # Unrelated Launcher widget is outside the entire cascade.
    foreign = mod.QWidget()
    foreign.parentWidget = lambda: None
    assert not guard.eventFilter(foreign, event)
    assert not root.isVisible()
    assert application.filters == []
    assert not application.applicationStateChanged.callbacks


def test_external_app_deactivation_closes_tool_without_ime_composition(nav):
    mod, _, launcher, _, root = _open(nav)
    application = mod.QApplication.instance()
    application._state = mod.Qt.ApplicationState.ApplicationInactive
    application.applicationStateChanged.emit(application._state)
    assert not root.isVisible()
    assert application.filters == []


def test_composing_ime_prevents_app_deactivation_dismissal(nav):
    mod, _, launcher, _, root = _open(nav)
    application = mod.QApplication.instance()
    root._search_edit.ime_composing = True
    application._state = mod.Qt.ApplicationState.ApplicationInactive
    application.applicationStateChanged.emit(application._state)
    assert root.isVisible()
    root._search_edit.ime_composing = False
    root.close()
