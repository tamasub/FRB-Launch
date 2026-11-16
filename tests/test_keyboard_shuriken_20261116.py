"""Keyboard -> physical-wheel shuriken: actual production dispatch, no Qt required."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from keyboard_shuriken_gate import (PageKeyShurikenGate, PAGE_FLIGHT_MAX_GAP_S,
                                    PAGE_FLIGHT_WINDOW_S)
from test_shuriken_scroll_inertia_20261105 import scroll_pad, FakeScrollBar, FakeListTree

APP = (ROOT / 'src/app.py').read_text('utf-8')
SCROLL = (ROOT / 'src/remote_shuriken_scroll.py').read_text('utf-8')


def test_four_distinct_same_direction_taps_only():
    gate = PageKeyShurikenGate()
    for i in range(3):
        assert gate.feed(-1, context='folder', now=i*.11) == 0
        assert gate.pending(context='folder', now=i*.11)
    assert gate.feed(-1, context='folder', now=.33) == -1
    assert not gate.pending(now=.34)
    assert gate.feed(1, context='folder', now=2) == 0
    assert gate.feed(1, context='folder', now=2.10, auto_repeat=True) == 0
    assert gate.feed(1, context='folder', now=2.18) == 0
    assert gate.feed(1, context='folder', now=2.26) == 0
    assert gate.feed(1, context='folder', now=2.34) == 1


def test_bursts_reset_on_gap_reverse_folder_switch_and_window():
    gate = PageKeyShurikenGate()
    gate.feed(1, context='A', now=1)
    gate.feed(1, context='A', now=1.1)
    assert gate.feed(-1, context='A', now=1.2) == 0
    assert not gate.feed(-1, context='B', now=1.3)
    assert not gate.feed(-1, context='B', now=1.3 + PAGE_FLIGHT_MAX_GAP_S + .01)
    assert not gate.pending(context='B', now=2.30)
    gate.reset()
    assert not gate.pending()
    # A gap-safe run can still time out on its cumulative span.
    t = 10
    for i in range(3):
        assert gate.feed(1, context='A', now=t + i * .45) == 0
    assert gate.feed(1, context='A', now=t + PAGE_FLIGHT_WINDOW_S + .01) == 0


def keyboard_handler():
    tree = ast.parse(APP)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Launcher')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'shuriken_keyboard_list_key')
    qt = NS(Key=NS(Key_Up=1, Key_Down=2, Key_PageUp=3, Key_PageDown=4, Key_Escape=5))
    namespace = {'Qt': qt, 'shuriken_trace': lambda *a, **kw: None}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 'shuriken_key_dispatch', 'exec'), namespace)
    return namespace['shuriken_keyboard_list_key'], qt


class FakeItem:
    def __init__(self, n):
        self.n = n


class ListTree(FakeListTree):
    def __init__(self, bar=None):
        super().__init__(bar or FakeScrollBar(position=2500, maximum=15000))
        self.rows = [FakeItem(i) for i in range(120)]
        self.current = self.rows[60]
    def topLevelItemCount(self): return len(self.rows)
    def topLevelItem(self, i): return self.rows[i]
    def currentItem(self): return self.current


class Event:
    def __init__(self, repeat=False): self.repeat = repeat
    def isAutoRepeat(self): return self.repeat


def demo(position=2500, current_index=60):
    handler, qt = keyboard_handler()
    module, pad = scroll_pad()
    tree = ListTree(FakeScrollBar(position=position, maximum=15000, page_step=500))
    tree.current = tree.rows[current_index]
    view = NS(middle=NS(tree=tree), current_directory=lambda:'F:/FRB/exp',
              _virtual_directory_node=None, row_data=lambda row: {'path':str(row.n)})
    launcher = NS(expanded_view=view, _shuriken_keyboard_gate=PageKeyShurikenGate())
    launcher.remote_window = NS(scroll_pad=pad)
    launcher.ensure_remote_window = lambda: launcher.remote_window
    launcher.auto_shuriken_scroll_files_list_target = lambda: tree
    pad.auto_target_provider = lambda: tree
    pad.auto_end_callback = lambda: None
    pad.scroll_requested.emit = lambda delta:tree.bar.setValue(tree.bar.value()+delta)
    return handler, qt, launcher, tree, pad, module


def test_third_page_native_fourth_starts_actual_shuriken_engine():
    handler, qt, launcher, tree, pad, module = demo()
    for i in range(3):
        assert handler(launcher, qt.Key.Key_PageDown, Event(), launcher.expanded_view.middle) is False
        tree.bar.setValue(tree.bar.value()+400)  # ordinary Qt page event
    assert handler(launcher, qt.Key.Key_PageDown, Event(), launcher.expanded_view.middle) is True
    assert pad._flight is not None and pad._flight.distance_px > 0
    assert pad._auto_wheel_source == 'keyboard'
    # Arrow DOWN matches downward travel; Arrow UP brakes it.
    assert handler(launcher, qt.Key.Key_Down, Event(), launcher.expanded_view.middle)
    assert pad._cruise_rate == module.WHEEL_ACCEL_FACTOR
    assert handler(launcher, qt.Key.Key_Up, Event(), launcher.expanded_view.middle)
    assert pad._cruise_rate == module.WHEEL_ACCEL_FACTOR * module.WHEEL_DECEL_FACTOR
    # Page key mid-flight never runs Qt's normal paging or parent hop.
    assert handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle)
    assert handler(launcher, qt.Key.Key_Escape, Event(), launcher.expanded_view.middle)
    assert pad._flight is None


def test_pageup_burst_at_first_row_suppresses_parent_between_taps():
    handler, qt, launcher, tree, pad, module = demo()
    assert handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle) is False
    tree.current = tree.rows[0]  # Qt PageUp landed at first row.
    assert handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle) is True
    assert handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle) is True
    assert handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle) is True
    assert pad._flight is not None and pad._flight.distance_px < 0
    pad._settle()
    # Already at first row before first PageUp: normal parent route is retained.
    tree.current = tree.rows[0]
    assert handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle) is False


def test_key_reverses_and_does_not_leak_into_other_columns_or_edit():
    handler, qt, launcher, tree, pad, module = demo()
    assert not handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle)
    assert not handler(launcher, qt.Key.Key_Down, Event(), launcher.expanded_view.middle)
    assert not launcher._shuriken_keyboard_gate.pending()
    for i in range(3):
        assert not handler(launcher, qt.Key.Key_PageDown, Event(), launcher.expanded_view.middle)
    # The fourth press must be in same directory as the first three.
    launcher.expanded_view.current_directory = lambda: 'F:/FRB/other'
    assert not handler(launcher, qt.Key.Key_PageDown, Event(), launcher.expanded_view.middle)
    assert pad._flight is None


def test_reverse_flight_arrow_mapping_and_natural_landing():
    handler, qt, launcher, tree, pad, module = demo()
    clock=[10.0]
    with patch.object(module.time, 'monotonic', side_effect=lambda:clock[0]), \
         patch('keyboard_shuriken_gate.time.monotonic', side_effect=lambda:clock[0]):
        for _ in range(4):
            result = handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle)
            clock[0]+=.08
        assert result is True
        assert pad._flight is not None and pad._flight.distance_px < 0
        assert handler(launcher, qt.Key.Key_Up, Event(), launcher.expanded_view.middle)
        assert pad._cruise_rate > 1
        assert handler(launcher, qt.Key.Key_Down, Event(), launcher.expanded_view.middle)
        assert pad._cruise_rate < module.WHEEL_ACCEL_FACTOR
        clock[0] += pad._flight.duration_s+1
        pad._scroll_tick()
        assert pad._flight is None
        assert tree.bar.value() == tree.bar.minimum()


def test_wiring_target_scope_unchanged_wheel_engine_reused():
    assert 'from keyboard_shuriken_gate import PageKeyShurikenGate' in APP
    assert 'self._shuriken_keyboard_gate = PageKeyShurikenGate()' in APP
    assert 'self.shuriken_keyboard_list_key' not in APP or 'shuriken_keyboard_list_key(' in APP
    assert 'self.shuriken_keyboard_list_key' not in SCROLL
    assert "self._auto_wheel_source in ('list', 'keyboard')" in SCROLL
    assert "remote.scroll_pad.start_from_wheel(fired, source='keyboard')" in APP
    assert 'view.go_up(keep_middle_focus=True)' in APP
    assert "return False  # Qt's real PageUp scrolling/selection." in APP


def test_original_parent_navigation_dispatch_at_first_row_still_works():
    # Execute the real Launcher.expanded_tree_key, not just inspect its text.
    module_tree = ast.parse(APP)
    cls = next(n for n in module_tree.body if isinstance(n, ast.ClassDef) and n.name == 'Launcher')
    function = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'expanded_tree_key')
    handler, qt, launcher, tree, pad, module = demo(current_index=0)
    tree.state = lambda: 'ready'
    tree.viewport = lambda: object()
    fake_qt = NS(Key=NS(**vars(qt.Key), Key_Delete=9, Key_C=10, Key_X=11,
                        Key_V=12, Key_F=13, Key_Right=14, Key_Left=15,
                        Key_Return=16, Key_Enter=17),
                 KeyboardModifier=NS(NoModifier=0, ControlModifier=2, AltModifier=4))
    ns = {'Qt': fake_qt, 'QAbstractItemView': NS(State=NS(EditingState='editing'))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 '<expanded_tree>', 'exec'), ns)
    parents = []
    view = launcher.expanded_view
    view.isVisible = lambda: True
    view.left = NS(tree=NS(viewport=lambda:object()))
    view.right = NS(tree=NS(viewport=lambda:object()))
    view.go_up = lambda **kwargs: parents.append(kwargs)
    launcher.page_key = lambda ev: False
    launcher.shuriken_keyboard_list_key = lambda k, ev, p: handler(launcher, k, ev, p)

    class KeyboardEvent(Event):
        accepted = False
        def key(self): return fake_qt.Key.Key_PageUp
        def modifiers(self): return 0
        def accept(self): self.accepted = True

    assert ns['expanded_tree_key'](launcher, tree, KeyboardEvent())
    assert parents == [{'keep_middle_focus':True}]
    tree.current = tree.rows[40]
    assert ns['expanded_tree_key'](launcher, tree, KeyboardEvent()) is False
    tree.current = tree.rows[0]
    for _ in range(3):
        assert ns['expanded_tree_key'](launcher, tree, KeyboardEvent())
    assert parents == [{'keep_middle_focus':True}]
    assert pad._flight is not None


def test_shuriken_page_fourth_at_scroll_edge_does_not_ascend_parent():
    handler, qt, launcher, tree, pad, module = demo(position=10, current_index=15)
    assert not handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle)
    tree.bar.setValue(0)
    tree.current = tree.rows[0]
    for _ in range(3):
        assert handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle)
    assert pad._flight is None
    # The next independent PageUp retains normal parent navigation.
    assert not handler(launcher, qt.Key.Key_PageUp, Event(), launcher.expanded_view.middle)
