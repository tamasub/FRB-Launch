"""(カレントフォルダー) Enter must keep Launch in front of Chrome.

The actual Windows Z-order transition needs a Windows GUI smoke test. These
portable tests cover native-focus authorization, no-steal conditions and the
real Qt.Tool Enter -> close -> List handoff using existing Qt test doubles.
"""
from types import SimpleNamespace

import windows
from test_slash_exp_navigation_20261118 import (FakeAction, Event, Item,
                                                Panel, make_launcher, nav)
from test_slash_exp_icon_and_focus_20261120 import _list_view_for_focus


def test_native_handoff_captures_only_our_foreground_tool(monkeypatch):
    tick = 12345
    state = {'foreground': 400, 'tick': tick}
    monkeypatch.setattr(windows, 'IS_WINDOWS', True)
    monkeypatch.setattr(windows, 'user', SimpleNamespace(IsWindow=lambda hwnd: hwnd in (400, 500, 600)), raising=False)
    monkeypatch.setattr(windows, 'foreground', lambda: state['foreground'])
    monkeypatch.setattr(windows, 'last_user_input_tick', lambda: state['tick'])
    monkeypatch.setattr(windows.time, 'monotonic', lambda: 777.0)

    monkeypatch.setattr(windows, '_menu_handoff_input_snapshot',
                        lambda: {'enter_down': True, 'pointer': (40, 50),
                                 'other_down': frozenset(), 'mouse_activity': False})
    ticket = windows.capture_menu_enter_handoff(400, 500)
    assert ticket[:3] == (400, 12345, 777.0)
    assert ticket[3]['initial']['enter_down'] is True
    state['foreground'] = 600  # Chrome already owns input: not our Enter!
    assert windows.capture_menu_enter_handoff(400, 500) is None
    state['foreground'] = 400
    state['tick'] = None
    assert windows.capture_menu_enter_handoff(400, 500) is None


def test_tool_close_can_restore_from_chrome_with_no_new_input(monkeypatch):
    current = 600  # Chrome rose behind the transient Qt.Tool menu
    calls = []
    monkeypatch.setattr(windows, 'IS_WINDOWS', True)
    monkeypatch.setattr(windows, 'user', SimpleNamespace(IsWindow=lambda hwnd: hwnd == 500), raising=False)
    monkeypatch.setattr(windows, 'last_user_input_tick', lambda: 12345)
    monkeypatch.setattr(windows, 'foreground', lambda: current)
    monkeypatch.setattr(windows.time, 'monotonic', lambda: 777.12)
    monkeypatch.setattr(windows, 'raise_normal_window', lambda hwnd: calls.append(('raise', hwnd)))
    monkeypatch.setattr(windows, 'activate_keyboard_window',
        lambda hwnd, expected_foreground: calls.append(('activate', hwnd, expected_foreground)) or True)

    assert windows.finish_menu_enter_handoff(500, (400, 12345, 777.0)) is True
    assert calls == [('raise', 500), ('activate', 500, 600)]


def test_native_menu_close_never_steals_after_new_input_or_timeout(monkeypatch):
    calls = []
    tick = {'value': 12346}
    now = {'value': 777.12}
    monkeypatch.setattr(windows, 'IS_WINDOWS', True)
    monkeypatch.setattr(windows, 'user', SimpleNamespace(IsWindow=lambda hwnd: True), raising=False)
    monkeypatch.setattr(windows, 'last_user_input_tick', lambda: tick['value'])
    monkeypatch.setattr(windows, 'foreground', lambda: 600)
    monkeypatch.setattr(windows.time, 'monotonic', lambda: now['value'])
    monkeypatch.setattr(windows, 'raise_normal_window', lambda hwnd: calls.append('raise'))
    monkeypatch.setattr(windows, 'activate_keyboard_window', lambda *a, **k: calls.append('activate'))

    ticket = (400, 12345, 777.0)
    assert windows.finish_menu_enter_handoff(500, ticket) is False  # a click on Chrome
    tick['value'] = 12345
    now['value'] = 779.0
    assert windows.finish_menu_enter_handoff(500, ticket) is False  # stale ticket
    assert windows.finish_menu_enter_handoff(500, None) is False
    assert calls == []


def test_enter_on_current_folder_restores_front_and_list(nav, tmp_path, monkeypatch):
    mod, key = nav
    directory = tmp_path / 'folder'
    directory.mkdir()
    launcher, calls = make_launcher()
    launcher.winId = lambda: 500
    launcher.activateWindow = lambda: calls.append(('activate_launcher',))
    view, tree, areas = _list_view_for_focus()
    launcher.expanded_view = view
    launcher.navigate_files_exp_folder = lambda path, **kw: calls.append(('folder', path)) or True
    menu = mod.SlashExpMenu(launcher, Panel([]))
    menu.winId = lambda: 400
    action = FakeAction()
    item = Item('（カレントフォルダー）', {'current_folder': True, 'path': str(directory)})
    menu._selected = lambda: (action, item)
    restored = []
    monkeypatch.setattr(mod.windows, 'IS_WINDOWS', True)
    monkeypatch.setattr(mod.windows, 'capture_menu_enter_handoff',
                        lambda menu_id, launch_id: (400, 12345, 777.0))
    monkeypatch.setattr(mod.windows, 'finish_menu_enter_handoff',
                        lambda launch_id, ticket: restored.append((launch_id, ticket)) or True)
    menu.keyPressEvent(Event(key.Key_Enter))

    assert ('folder', str(directory)) in calls
    assert areas == ['list']
    assert tree.current is tree.rows[0]
    assert len(tree.focuses) == 1
    assert restored and all(r == (500, (400, 12345, 777.0)) for r in restored)


def test_unrelated_folder_or_file_does_not_request_foreground(nav, tmp_path, monkeypatch):
    mod, key = nav
    directory = tmp_path / 'folder'
    directory.mkdir()
    launcher, calls = make_launcher()
    launcher.winId = lambda: 500
    view, _, _ = _list_view_for_focus()
    launcher.expanded_view = view
    launcher.navigate_files_exp_folder = lambda path, **kw: True
    menu = mod.SlashExpMenu(launcher, Panel([]))
    captured = []
    monkeypatch.setattr(mod.windows, 'IS_WINDOWS', True)
    monkeypatch.setattr(mod.windows, 'capture_menu_enter_handoff',
                        lambda *args: captured.append(args) or (400, 12345, 777.0))
    menu._selected = lambda: (FakeAction(), Item('folder', {'path': str(directory)}))
    menu.keyPressEvent(Event(key.Key_Enter))
    assert captured == []


def test_native_recovery_precedes_directory_navigation(nav, tmp_path, monkeypatch):
    """Do not wait for Enter KEYUP before the first native restore attempt."""
    mod, key = nav
    directory = tmp_path / 'folder'
    directory.mkdir()
    launcher, _ = make_launcher()
    launcher.winId = lambda: 500
    launcher.activateWindow = lambda: None
    view, _, _ = _list_view_for_focus()
    launcher.expanded_view = view
    order = []
    launcher.navigate_files_exp_folder = lambda path, **kw: order.append('navigate') or True
    menu = mod.SlashExpMenu(launcher, Panel([]))
    menu.winId = lambda: 400
    menu._selected = lambda: (FakeAction(),
        Item('（カレントフォルダー）', {'current_folder': True, 'path': str(directory)}))
    original_close = menu.close
    def close():
        order.append('close')
        return original_close()
    menu.close = close
    monkeypatch.setattr(mod.windows, 'IS_WINDOWS', True)
    monkeypatch.setattr(mod.windows, 'capture_menu_enter_handoff',
                        lambda *args: (400, 12345, 777.0))
    monkeypatch.setattr(mod.windows, 'finish_menu_enter_handoff',
                        lambda *args: order.append('native_restore') or True)
    menu.keyPressEvent(Event(key.Key_Enter))
    assert order[:3] == ['close', 'native_restore', 'navigate']
