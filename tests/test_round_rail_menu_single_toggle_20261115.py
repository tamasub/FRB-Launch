"""ぐりぐりレール第5弾: QMenu一意性、Exp開閉トグル、60px配置。Qt無しで実行。"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1] / 'src'
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
REMOTE = (ROOT / 'launch_remote.py').read_text(encoding='utf-8')
EXP = (ROOT / 'remote_files_explorer.py').read_text(encoding='utf-8')
VIEW = (ROOT / 'expanded_view.py').read_text(encoding='utf-8')
WHEEL = (ROOT / 'remote_context_wheel.py').read_text(encoding='utf-8')


def method(source, class_name, name, ctx=None):
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == class_name)
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name == name)
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    namespace = dict(ctx or {})
    exec(compile(module, '<method>', 'exec'), namespace)
    return namespace[name]


class MockMenu:
    def __init__(self, title):
        self.title, self.visible, self.closes = title, False, 0
        self.aboutToHide = NS(connect=lambda fn: None)

    def isVisible(self):
        return self.visible

    def close(self):
        self.visible = False
        self.closes += 1

    def popup(self, point):
        self.visible = True


class RemoteOwner:
    """Launcherの公開メソッドを再利用し、実QMenuを模擬する。"""

    def __init__(self, *, selected):
        self.menu_list = []
        self._launch_context_menu = None
        self.selected = selected
        self.pad = NS(width=lambda: 60,
                      mapToGlobal=lambda point: ('pad', point))
        self._remote_pad_context_active = False
        self._remote_pad_context_menu = None
        self.enabled = []

    def _active_remote_wheel_pad(self):
        return self.pad

    def _show_remote_target_context_menu(self):
        if self.selected:
            menu = MockMenu('item-context')
            self.menu_list.append(menu)
            self._launch_context_menu = menu
            menu.popup((20, 20))

    def _create_files_context_menu(self, parent):
        menu = MockMenu('fallback')
        self.menu_list.append(menu)
        return menu

    def _prepend_remote_pad_navigation(self, menu, force=False):
        return True

    def _wire_hybrid_context_menu(self, menu):
        return None

    def _forget_launch_context_menu(self, menu):
        if self._launch_context_menu is menu:
            self._launch_context_menu = None

    def _enable_remote_context_wheel_for_menu(self, menu):
        self.enabled.append(menu)


def test_remote_pad_does_not_open_fallback_after_item_menu():
    dispatch = method(APP, 'LaunchApp', 'remote_context_menu',
                      {'QPoint': lambda x, y: (x, y)}) if 'class LaunchApp(' in APP else None
    if dispatch is None:
        owner_class = next(n.name for n in ast.parse(APP).body
                           if isinstance(n, ast.ClassDef)
                           and any(isinstance(m, ast.FunctionDef)
                                   and m.name == 'remote_context_menu' for m in n.body))
        dispatch = method(APP, owner_class, 'remote_context_menu',
                          {'QPoint': lambda x, y: (x, y)})
    owner = RemoteOwner(selected=True)
    dispatch(owner)
    assert [m.title for m in owner.menu_list] == ['item-context']
    assert len([m for m in owner.menu_list if m.visible]) == 1
    assert owner.enabled == [owner.menu_list[0]]
    dispatch(owner)
    assert owner.menu_list[0].closes == 1
    assert len([m for m in owner.menu_list if m.visible]) == 1
    assert all(m.title == 'item-context' for m in owner.menu_list)


def test_empty_remote_pad_opens_one_tracked_fallback():
    owner_class = next(n.name for n in ast.parse(APP).body
                       if isinstance(n, ast.ClassDef)
                       and any(isinstance(m, ast.FunctionDef)
                               and m.name == 'remote_context_menu' for m in n.body))
    dispatch = method(APP, owner_class, 'remote_context_menu',
                      {'QPoint': lambda x, y: (x, y)})
    owner = RemoteOwner(selected=False)
    dispatch(owner)
    assert [m.title for m in owner.menu_list] == ['fallback']
    assert owner._launch_context_menu is owner.menu_list[0]
    assert owner.menu_list[0].visible


def test_opened_folder_closes_and_closed_folder_activates():
    toggle = method(EXP, 'RemoteFilesExplorer', 'remote_toggle_current')
    state = NS(expanded=True, selections=[], activated=0, saved=0, stopped=0)
    class Obj:
        pass
    obj = Obj()
    obj.tree = NS(currentIndex=lambda: NS(isValid=lambda: True),
                  isExpanded=lambda idx: state.expanded,
                  collapse=lambda idx: setattr(state, 'expanded', False))
    obj._selection_timer = NS(stop=lambda: setattr(state, 'stopped', state.stopped+1))
    obj._schedule_tree_state_save = lambda: setattr(state, 'saved', state.saved+1)
    obj.remote_activate_current = lambda: setattr(state, 'activated', state.activated+1) or True
    assert toggle(obj) and not state.expanded
    assert state.stopped == 1 and state.saved == 1
    assert state.activated == 0
    assert toggle(obj) and state.activated == 1


def test_exp_click_uses_toggle_only_for_round_mode():
    owner_class = next(n.name for n in ast.parse(APP).body
                       if isinstance(n, ast.ClassDef)
                       and any(isinstance(m, ast.FunctionDef)
                               and m.name == '_remote_exp_single_click' for m in n.body))
    click = method(APP, owner_class, '_remote_exp_single_click')
    calls = []
    panel = NS(remote_toggle_current=lambda: calls.append('toggle'),
               remote_activate_current=lambda: calls.append('legacy'))
    view = NS(isVisible=lambda: True, _workspace_mode='files')
    obj = NS(expanded_view=view, _remote_area='files_exp',
             _remote_popup_area=None, _current_remote_files_exp=lambda: panel,
             remote_focus_area=lambda target: calls.append('focus'),
             remote_display_mode='wheel')
    click(obj)
    assert calls == ['toggle', 'focus']
    calls.clear()
    obj.remote_display_mode = 'window'
    click(obj)
    assert calls == ['legacy', 'focus']


def test_round_context_event_is_consumed_and_geometry_keeps_list_margin():
    event_method = method(REMOTE, 'RoundRailWheelPad', 'contextMenuEvent')
    event = NS(accepted=False)
    event.accept = lambda: setattr(event, 'accepted', True)
    event_method(object(), event)
    assert event.accepted
    assert 'self.setFixedSize(60, 60)' in REMOTE
    assert 'self.rail_wheel.setFixedSize(60, 60)' in VIEW
    assert 'center.x() - pad.width() // 2 - 6' in VIEW
    assert 'QRegion(self.rail_wheel.rect(), QRegion.RegionType.Ellipse)' in VIEW


def test_tool_menu_outside_click_can_reach_embedded_pad():
    hit = method(WHEEL, 'RemoteContextWheel', '_hit')
    pad = NS(isVisible=lambda: True, rect=lambda: NS(contains=lambda p: p == (5, 5)),
             mapFromGlobal=lambda p: p)
    obj = NS(launcher=NS(_active_remote_wheel_pad=lambda: pad))
    assert hit(obj, (5, 5)) == 'CLICK'
    assert hit(obj, (100, 100)) is None
