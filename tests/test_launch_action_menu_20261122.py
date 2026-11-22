"""Ctrl+Menu v0.1: physical-key recognition and legacy action dispatch.

Pure-model and extracted-method tests run without a Windows desktop/PySide6;
manual acceptance still checks Qt's native keyboard context event ordering.
"""
import ast
from enum import Flag
from pathlib import Path
from types import SimpleNamespace as NS
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from launch_action_menu_model import (LAUNCH_ACTIONS, action_is_available,
                                      is_ctrl_menu_key)


class Mod(Flag):
    No = 0
    Ctrl = 0x04000000
    Shift = 0x02000000
    Alt = 0x08000000
    Keypad = 0x20000000


class Event:
    def __init__(self, kind, key=0, mods=0, vk=0, reason='keyboard', repeat=False):
        self.kind, self.k, self.mods, self.vk = kind, key, mods, vk
        self.reason_value, self.repeat = reason, repeat
        self.accepted = False
    def type(self): return self.kind
    def key(self): return self.k
    def modifiers(self): return self.mods
    def nativeVirtualKey(self): return self.vk
    def isAutoRepeat(self): return self.repeat
    def reason(self): return self.reason_value
    def accept(self): self.accepted = True


def method_from(file, method_name, env):
    source = ast.parse((ROOT / 'src' / file).read_text(encoding='utf-8'))
    cls = next(c for c in source.body if isinstance(c, ast.ClassDef)
               and any(isinstance(m, ast.FunctionDef) and m.name == method_name
                       for m in c.body))
    method = next(m for m in cls.body if isinstance(m, ast.FunctionDef)
                  and m.name == method_name)
    ns = dict(env)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],
             type_ignores=[])), str(ROOT / 'src' / file), 'exec'), ns)
    return ns[method_name]


def test_physical_ctrl_menu_recognizes_pyside6_enums_and_never_hijacks_plain_menu():
    assert is_ctrl_menu_key(0x01000055, Mod.Ctrl, 0x5d)
    assert is_ctrl_menu_key(0x01000055, Mod.Ctrl | Mod.Keypad, 0)
    assert is_ctrl_menu_key(0, Mod.Ctrl, 0x5d)
    for mods in (Mod.No, Mod.Shift, Mod.Ctrl | Mod.Shift,
                 Mod.Ctrl | Mod.Alt):
        assert not is_ctrl_menu_key(0x01000055, mods, 0x5d)
    assert not is_ctrl_menu_key(0x46, Mod.Ctrl, 0x46), 'Ctrl+F unchanged'


def test_four_stable_actions_and_files_only_guard():
    assert [name for name, *_ in LAUNCH_ACTIONS] == [
        'launch_search_history', 'breadcrumb_history',
        'folder_search_history', 'launch_settings']
    assert all(action_is_available(name, True) for name, *_ in LAUNCH_ACTIONS)
    assert action_is_available('launch_search_history', False)
    assert action_is_available('launch_settings', False)
    assert not action_is_available('breadcrumb_history', False)
    assert not action_is_available('folder_search_history', False)
    assert not action_is_available('unknown', True)


def test_ctrl_menu_event_bridge_opens_once_even_with_duplicate_native_context_event():
    calls = []
    window = NS(open_launch_action_menu=lambda **kw: calls.append(kw))
    owner = NS(launcher=window, _launch_owns_keyboard_source=lambda obj: True)
    types = NS(KeyPress='press', KeyRelease='release', ContextMenu='context')
    ctx = NS(Reason=NS(Keyboard='keyboard'))
    fn = method_from('expanded_view.py', '_launch_action_menu_keyboard', {
        'QEvent': NS(Type=types), 'QApplication': NS(
            activeModalWidget=lambda: None,
            keyboardModifiers=lambda: Mod.Ctrl.value),
        'is_ctrl_menu_key': is_ctrl_menu_key,
        'Qt': NS(KeyboardModifier=NS(ControlModifier=Mod.Ctrl.value)),
        'QWidget': object, 'QContextMenuEvent': ctx,
    })
    obj = object()
    press = Event('press', 0x01000055, Mod.Ctrl, 0x5d)
    assert fn(owner, obj, press) and press.accepted
    assert calls == [{'source': obj}]
    # Secondary native keyboard ContextMenu event must not open a second menu.
    # Simulate the PySide6.QtGui import performed in production.
    from types import ModuleType
    import sys as _sys
    old = _sys.modules.get('PySide6.QtGui')
    pkg = _sys.modules.get('PySide6')
    try:
        if pkg is None:
            _sys.modules['PySide6'] = ModuleType('PySide6')
        fake_gui = ModuleType('PySide6.QtGui')
        fake_gui.QContextMenuEvent = ctx
        _sys.modules['PySide6.QtGui'] = fake_gui
        native = Event('context')
        assert fn(owner, obj, native) and native.accepted
    finally:
        if old is None: _sys.modules.pop('PySide6.QtGui', None)
        else: _sys.modules['PySide6.QtGui'] = old
        if pkg is None: _sys.modules.pop('PySide6', None)
    assert len(calls) == 1
    # Ctrl+F is never captured by the new bridge.
    assert not fn(owner, obj, Event('press', 0x46, Mod.Ctrl, 0x46))
    assert len(calls) == 1


def test_actions_call_existing_owners_no_synthetic_key_replay():
    calls = []
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              show_directory_favorites=lambda: calls.append('G') or True,
              show_middle_search_history=lambda: calls.append('H') or True)
    launcher = NS(expanded_view=view,
                  show_history_popup=lambda: calls.append('history'),
                  open_theme_menu=lambda: calls.append('I'))
    execute = method_from('app.py', 'execute_launch_action', {
        'action_is_available': action_is_available})
    for action_id, *_ in LAUNCH_ACTIONS:
        assert execute(launcher, action_id)
    assert calls == ['history', 'G', 'H', 'I']
    view._workspace_mode = 'browser'
    assert not execute(launcher, 'breadcrumb_history')
    assert not execute(launcher, 'folder_search_history')
    assert not execute(launcher, 'unknown')


def test_launch_action_menu_qss_has_round_corners_and_symmetric_vertical_padding():
    from launch_appearance import launch_action_menu_qss
    qss = launch_action_menu_qss('light')
    assert 'QMenu#frbLaunchActionMenu' in qss
    assert 'border-radius:10px' in qss
    assert 'padding:8px 6px 8px 6px' in qss


def test_files_mode_launch_action_menu_uses_fixed_upper_left_lane_anchor():
    calls = []
    class Header:
        def isVisible(self): return True
        def height(self): return 24
    class Tree:
        def isVisible(self): return True
        def header(self): return Header()
        def mapToGlobal(self, point):
            calls.append((point.x(), point.y()))
            return ('global', point.x(), point.y())
    view = NS(isVisible=lambda: True, _workspace_mode='files', middle=NS(tree=Tree()))
    owner = NS(expanded_view=view, theme_button=None)
    method = method_from('app.py', '_launch_action_menu_point', {
        'QWidget': object, 'QAbstractItemView': object, 'QPoint': lambda x, y: NS(x=lambda: x, y=lambda: y),
    })
    assert method(owner) == ('global', 8, 30)
    assert calls == [(8, 30)]
