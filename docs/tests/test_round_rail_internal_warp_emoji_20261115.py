"""ぐりぐりレール: 23:09版の列切替ワープと中央絵文字。Qt不要。"""
import ast
from pathlib import Path
import sys

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
from test_round_rail_context_pointer_follow_20261115 import _launcher, Cursor

ROOT = TESTS.parent / 'src'
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
REMOTE = (ROOT / 'launch_remote.py').read_text(encoding='utf-8')


class RoundPad:
    def __init__(self, *, visible=True):
        self.visible = visible
        self.targets = []

    def isVisible(self):
        return self.visible

    def width(self):
        return 60

    def height(self):
        return 60

    def mapToGlobal(self, point):
        # 60px円の中心は (230,330)。カーソルは必ず内側へ。
        return (200 + point[0], 300 + point[1])


def _test_owner(target, *, mode='wheel', auto=True, visible=True):
    owner, menu, calls, drain, exp_tree, list_tree = _launcher(auto)
    pad = RoundPad(visible=visible)
    owner.remote_display_mode = mode
    owner.expanded_view.rail_wheel = pad
    owner.expanded_view.rail_wheel_select_side = pad.targets.append
    owner._dispatch_files_column_context_navigation(menu, target)
    drain()
    return owner, calls, pad, exp_tree, list_tree


def test_round_mode_list_menu_warp_stays_inside_right_half():
    owner, calls, pad, exp, lst = _test_owner('directory')
    assert calls == ['close', 'directory']
    assert Cursor.moves == [(245, 330)]
    assert pad.targets == ['directory']
    assert not exp.scrolled and not lst.scrolled


def test_round_mode_exp_menu_warp_stays_inside_left_half():
    owner, calls, pad, exp, lst = _test_owner('files_exp')
    assert calls == ['close', 'files_exp']
    assert Cursor.moves == [(215, 330)]
    assert pad.targets == ['files_exp']
    assert not exp.scrolled and not lst.scrolled


def test_not_round_remote_window_keeps_old_far_warp():
    _, _, pad, exp, _ = _test_owner('files_exp', mode='window')
    assert Cursor.moves == [(180, 31)]
    assert not pad.targets
    assert exp.scrolled


def test_not_round_column15_keeps_old_far_warp():
    _, _, pad, _, lst = _test_owner('directory', mode='column15')
    assert Cursor.moves == [(580, 31)]
    assert not pad.targets
    assert lst.scrolled


def test_warp_disabled_moves_nothing_in_any_mode():
    for mode in ('wheel', 'off', 'window'):
        _, _, pad, exp, lst = _test_owner('directory', mode=mode, auto=False)
        assert Cursor.moves == []
        assert pad.targets == []
        assert not exp.scrolled and not lst.scrolled


def test_hidden_round_button_does_not_warp_elsewhere():
    _, _, pad, exp, lst = _test_owner('directory', visible=False)
    assert Cursor.moves == []
    assert pad.targets == []
    assert not exp.scrolled and not lst.scrolled


def test_user_pointer_move_cancels_delayed_round_warp():
    owner, menu, calls, drain, exp, lst = _launcher(True)
    pad = RoundPad()
    owner.remote_display_mode = 'wheel'
    owner.expanded_view.rail_wheel = pad
    owner.expanded_view.rail_wheel_select_side = pad.targets.append
    owner._dispatch_files_column_context_navigation(menu, 'directory')
    Cursor.current = (99, 88)
    drain()
    assert Cursor.moves == []
    assert pad.targets == []


def test_center_emoji_is_original_remote_glyph_and_mouse_transparent():
    tree = ast.parse(REMOTE)
    pad_class = next(c for c in tree.body if isinstance(c, ast.ClassDef)
                     and c.name == 'RoundRailWheelPad')
    init = next(n for n in pad_class.body if isinstance(n, ast.FunctionDef)
                and n.name == '__init__')
    init_source = ast.get_source_segment(REMOTE, init)
    assert "glyph = QLabel('🔘', self)" in REMOTE  # 元のRemoteと同一絵文字
    assert "self._center_glyph = QLabel('🔘', self)" in init_source
    assert 'WA_TransparentForMouseEvents' in init_source
    assert 'self._center_glyph.setGeometry(19, 20, 22, 22)' in init_source
    assert 'self._center_glyph.raise_()' in init_source
    paint = next(n for n in pad_class.body if isinstance(n, ast.FunctionDef)
                 and n.name == 'paintEvent')
    paint_source = ast.get_source_segment(REMOTE, paint)
    assert 'QPointF(center_x, 42.0)' in paint_source
    assert "'Exp'" in paint_source and "'List'" in paint_source
    assert 'painter.end()' in paint_source


def test_the_arrowed_round_doubleclick_still_targets_inside_button():
    view = (ROOT / 'expanded_view.py').read_text(encoding='utf-8')
    assert 'pad.width() * 3 // 4' in view
    assert 'pad.height() // 2' in view
    assert "self.rail_wheel_select_side('directory')" in view
