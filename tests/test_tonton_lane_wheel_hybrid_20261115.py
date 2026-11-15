"""List tonton rail: same wheel engine as rows, no synthetic left/right keys.

This is a pure-Python executable contract test. Windows Qt mouse routing needs
its own final hands-on check (PySide6 is not installed in this environment).
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SOURCE = (Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py').read_text(encoding='utf-8')


def _method(name):
    tree = ast.parse(SOURCE)
    owner = next(node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == 'ExpandedLauncherView')
    method = next(node for node in owner.body
                  if isinstance(node, ast.FunctionDef) and node.name == name)
    return method


class Wheel:
    def __init__(self, angle=-120, pixel=0, modifiers=0):
        self.angle, self.pixel, self.mods = angle, pixel, modifiers
    def modifiers(self): return self.mods
    def angleDelta(self): return NS(y=lambda: self.angle)
    def pixelDelta(self): return NS(y=lambda: self.pixel)


class Tree:
    def __init__(self, owner):
        self.owner = owner
        self.wheels = []
    def wheelEvent(self, event):
        self.wheels.append((event.angleDelta().y(), self.owner._middle_lane_wheel_active))
        if event.angle == 999:
            raise RuntimeError('forced diagnostic failure')


namespace = {
    'Qt': NS(KeyboardModifier=NS(NoModifier=0), MouseButton=NS(NoButton=0)),
    'QApplication': NS(mouseButtons=lambda: 0),
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[_method('wheel_middle_from_tonton_lane')],
                                               type_ignores=[])), '<lane>', 'exec'), namespace)
route = namespace['wheel_middle_from_tonton_lane']


class Demo:
    wheel_middle_from_tonton_lane = route
    def __init__(self):
        self._workspace_mode = 'files'
        self.middle = NS(tree=Tree(self))
        self._middle_lane_wheel_active = False
        self.synced = []
    def isVisible(self): return True
    def _sync_remote_area_after_mouse_press(self, value): self.synced.append(value)


def test_plain_lane_wheel_uses_tree_engine_once_and_keeps_lane_identity():
    demo = Demo()
    assert demo.wheel_middle_from_tonton_lane(Wheel())
    assert demo.middle.tree.wheels == [(-120, True)]
    assert demo.synced == ['directory']
    assert demo._middle_lane_wheel_active is False
    assert demo.wheel_middle_from_tonton_lane(Wheel(120))
    assert demo.middle.tree.wheels[-1] == (120, True)


def test_modifiers_empty_wheel_hidden_workspace_and_pressed_button_are_ignored():
    demo = Demo()
    assert not demo.wheel_middle_from_tonton_lane(Wheel(modifiers=1))
    assert not demo.wheel_middle_from_tonton_lane(Wheel(0, 0))
    demo._workspace_mode = 'browser'
    assert not demo.wheel_middle_from_tonton_lane(Wheel())
    demo._workspace_mode = 'files'
    original = namespace['QApplication']
    namespace['QApplication'] = NS(mouseButtons=lambda: 1)
    try:
        assert not demo.wheel_middle_from_tonton_lane(Wheel())
    finally:
        namespace['QApplication'] = original
    assert demo.middle.tree.wheels == []


def test_flag_always_restored_even_if_tree_engine_raises():
    demo = Demo()
    try:
        demo.wheel_middle_from_tonton_lane(Wheel(999))
    except RuntimeError:
        pass
    else:
        raise AssertionError('expected forced diagnostic failure')
    assert demo._middle_lane_wheel_active is False


def test_edge_wheel_uses_current_row_without_warp_when_cursor_is_on_lane():
    from test_wan_middle_files_20261025 import Demo as EdgeDemo, Event, Mouse, World, Coord
    Mouse.current = Coord(-10, 50)  # physically left of viewport, inside tonton lane
    Mouse.moves = []
    World.calls = []
    World.buttons = 0
    demo = EdgeDemo(size=6, hovered=4)
    demo.launcher = NS(pointer_warp_enabled=True)
    demo._middle_lane_wheel_active = True
    tree = demo.middle.tree
    tree.current = tree.items[2]
    assert demo.wheel_middle_at_edge(Event(degrees=-120), 0, 0)
    assert tree.current is tree.items[3]
    assert Mouse.moves == []
    assert World.calls == []
    assert demo._middle_follow_pending is None
    assert demo.wheel_middle_at_edge(Event(degrees=120), 0, 0)
    assert tree.current is tree.items[2]
    assert demo.events == []  # No file activation or folder navigation


def test_normal_wheel_outside_list_viewport_is_still_ignored():
    from test_wan_middle_files_20261025 import Demo as EdgeDemo, Event, Mouse, Coord
    Mouse.current = Coord(-10, 50)
    demo = EdgeDemo(size=6, hovered=4)
    demo._middle_lane_wheel_active = False
    assert not demo.wheel_middle_at_edge(Event(), 0, 0)


def test_event_routing_is_lane_only_and_click_contract_remains():
    owner = next(n for n in ast.parse(SOURCE).body
                 if isinstance(n, ast.ClassDef) and n.name == 'ExpandedLauncherView')
    filt = next(n for n in owner.body
                if isinstance(n, ast.FunctionDef) and n.name == 'eventFilter')
    filt_source = ast.get_source_segment(SOURCE, filt)
    assert "obj is getattr(self, 'middle_back_lane', None)" in filt_source
    assert 'self.wheel_middle_from_tonton_lane(event)' in filt_source
    assert 'self.handle_middle_back_double_click(obj, event)' in filt_source
    assert 'self.show_lane_new_menu(event.globalPos())' in filt_source
    # No interception in Exp; no left-hold to pretend to be an arrow key.
    handler = ast.get_source_segment(SOURCE, _method('wheel_middle_from_tonton_lane'))
    assert 'Key_Right' not in handler and 'Key_Left' not in handler
    assert 'self.middle.tree.wheelEvent(event)' in handler
