"""2026-11-21: Web '+' must not cover QTabBar's native scroll arrows.

Logic-only geometry regression checks; Windows/Qt GUI confirmation is still needed.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

SOURCE = (Path(__file__).resolve().parents[1] / 'src' / 'launch_web_view.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == '_WebTabBar')


class QPoint:
    def __init__(self, x, y):
        self._x, self._y = x, y
    def x(self): return self._x
    def y(self): return self._y


def method(name):
    node = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {'QPoint': QPoint}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<web-tab-layout>', 'exec'), namespace)
    return namespace[name]


class Button:
    def __init__(self):
        self.xy = None
        self.visible = True
        self.raised = False
    def width(self): return 29
    def height(self): return 29
    def move(self, x, y): self.xy = (x, y)
    def show(self): self.visible = True
    def hide(self): self.visible = False
    def raise_(self): self.raised = True


class Bar:
    def __init__(self, *, host_width=500, width=450, last_right=1200,
                 first_left=0, origin=0):
        self.host = SimpleNamespace(width=lambda: host_width)
        self._width = width
        self._origin = origin
        self._last_right = last_right
        self._first_left = first_left
        self._new_tab_button = Button()
        self._max_width = 16777215
    def parentWidget(self): return self.host
    def maximumWidth(self): return self._max_width
    def setMaximumWidth(self, width): self._max_width = width
    def width(self): return self._width
    def height(self): return 33
    def count(self): return 5
    def mapTo(self, host, point):
        assert host is self.host
        return SimpleNamespace(x=lambda: self._origin + point.x(), y=lambda: point.y())
    def tabRect(self, index):
        if index == 0:
            return SimpleNamespace(left=lambda: self._first_left)
        assert index == 4
        return SimpleNamespace(right=lambda: self._last_right)
    def reserve_new_tab_space(self): method('reserve_new_tab_space')(self)


def test_plus_after_native_right_scroll_arrow():
    bar = Bar(host_width=500, width=450, last_right=1200)
    method('position_new_tab_button')(bar)
    assert bar._new_tab_button.visible
    assert bar._new_tab_button.xy[0] >= 450 + 6
    assert bar._new_tab_button.xy[0] + 29 <= 500 - 4


def test_plus_does_not_move_back_over_scroll_arrows_when_scrolled_to_last_tab():
    bar = Bar(host_width=500, width=450, last_right=435, first_left=-300)
    method('position_new_tab_button')(bar)
    assert bar._new_tab_button.visible
    assert bar._new_tab_button.xy[0] >= 450 + 6


def test_plus_does_not_overlay_arrow_during_transient_relayout():
    bar = Bar(host_width=500, width=490, last_right=1300)
    method('position_new_tab_button')(bar)
    assert not bar._new_tab_button.visible
    assert bar._max_width == 455  # 500 - 29 - 16
    # Qt later lays out the shortened bar and schedules reposition.
    bar._width = 455
    method('position_new_tab_button')(bar)
    assert bar._new_tab_button.visible
    assert bar._new_tab_button.xy[0] == 462


def test_reservation_accounts_for_tabbar_origin_and_very_narrow_host():
    bar = Bar(host_width=90, width=75, last_right=200, origin=8)
    method('reserve_new_tab_space')(bar)
    assert bar._max_width == 37  # 90 - 29 - 16 - 8
    bar.host = SimpleNamespace(width=lambda: 68)
    method('reserve_new_tab_space')(bar)
    assert bar._max_width == 15  # No old forced 40px overlap


def test_normal_tab_placement_stays_directly_after_last_tab():
    bar = Bar(host_width=900, width=326, last_right=325, first_left=0)
    method('position_new_tab_button')(bar)
    assert bar._new_tab_button.xy == (333, 2)
