"""FRBぐりぐりレール: 右/左半円の操作責務と長押し無効の回帰テスト。"""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from rail_wheel_model import rail_target_from_x, rail_long_press_consumed


def test_cursor_x_selects_half_including_center_boundary():
    for width in (52, 64, 100):
        assert rail_target_from_x(0, width) == 'files_exp'
        assert rail_target_from_x(width / 2 - .01, width) == 'files_exp'
        assert rail_target_from_x(width / 2, width) == 'directory'
        assert rail_target_from_x(width - 1, width) == 'directory'


def test_long_press_does_not_commit_a_click():
    assert not rail_long_press_consumed(0)
    assert not rail_long_press_consumed(449)
    assert rail_long_press_consumed(450)
    assert rail_long_press_consumed(700)


def _read(name):
    text = (ROOT / 'src' / name).read_text(encoding='utf-8')
    ast.parse(text)
    return text


def test_round_pad_is_a_separate_variant_preserving_normal_remote():
    remote = _read('launch_remote.py')
    assert 'class RoundRailWheelPad(WheelPad):' in remote
    assert 'class WheelPad(QFrame):' in remote
    assert 'self.target_switch_allowed = lambda: False' in remote
    assert 'self._press_clock = QElapsedTimer()' in remote
    assert 'if long_held and not self._ignore_double_release:' in remote
    assert 'self._hide_target_menu()' in remote
    assert 'self._pressed = False' in remote


def test_wheel_click_doubleclick_select_side_before_dispatch():
    remote = _read('launch_remote.py')
    klass = ast.parse(remote)
    pad = next(n for n in klass.body if isinstance(n, ast.ClassDef)
               and n.name == 'RoundRailWheelPad')
    for method in ('wheelEvent', 'mousePressEvent', 'mouseReleaseEvent',
                   'mouseDoubleClickEvent', 'mouseMoveEvent'):
        body = next(n for n in pad.body if isinstance(n, ast.FunctionDef)
                    and n.name == method)
        assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == '_side_from_event'
                   for n in ast.walk(body)), method
    assert 'self.side_changed.emit(target)' in remote


def test_antialiased_inset_circle_and_center_dotted_divider():
    remote = _read('launch_remote.py')
    assert 'painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)' in remote
    assert 'QRectF(2.0, 2.0, self.width() - 4.0, self.height() - 4.0)' in remote
    assert 'Qt.PenStyle.DotLine' in remote
    assert "'Exp'" in remote and "'List'" in remote
    view = _read('expanded_view.py')
    assert 'self.rail_wheel = RoundRailWheelPad(self)' in view
    assert 'self.rail_wheel.side_changed.connect(self.rail_wheel_select_side)' in view
    assert 'self.launcher.set_files_operating_target(target)' in view
    assert 'pad.set_circle_theme(fill, border, ink)' in view
    assert 'self.files_splitter.splitterMoved.connect(' in view


def test_embedded_exp_is_used_when_remote_window_is_absent():
    app = _read('app.py')
    assert "getattr(self, 'remote_display_mode', 'off') == 'wheel'" in app
    source = app[app.index('    def _current_remote_files_exp(self):'):]
    source = source.split('\n    def ', 1)[0]
    assert "return getattr(view, 'embedded_files_exp', None)" in source
