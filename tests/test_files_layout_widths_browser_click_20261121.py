"""Desired-vs-rendered width invariants and URL select-all without native Qt.

The real Qt splitter and WebEngine must additionally be checked on Windows.
"""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from files_layout_widths import (desired_exp_width, resize_with_fixed_exp,
                                 maximize_with_fixed_exp_and_name)


def test_exp_saved_px_ignores_proportional_width_growth():
    # Windows maximize: a 275px first pane may grow to 540px by Qt stretch.
    assert resize_with_fixed_exp([540, 1460], 275) == [275, 1725]
    assert resize_with_fixed_exp([275, 725], 275) == [275, 725]
    assert resize_with_fixed_exp([700, 2100], 400) == [400, 2400]


def test_exp_clamps_temporarily_on_unusably_narrow_window():
    collapsed = resize_with_fixed_exp([100, 200], 400, list_min=170)
    # This cannot fit 400+170, but the stored desired width stays untouched.
    assert sum(collapsed) == 300
    assert collapsed[0] <= 300
    assert desired_exp_width('400') == 400


def test_third_max_uses_saved_exp_and_saved_name_not_other_columns():
    sizes = [300, 420, 780]
    out = maximize_with_fixed_exp_and_name(
        sizes, 2, exp_width=280, name_width=440, back_lane=24,
        list_chrome=8)
    assert out == [280, 472, 748]
    assert sum(out) == sum(sizes)
    # Nothing is persisted: caller can restore its separate 3-pane snapshot.
    assert sizes == [300, 420, 780]


def test_third_max_name_column_works_with_hidden_sibling():
    sizes = [300, 400, 0, 600]
    out = maximize_with_fixed_exp_and_name(
        sizes, 3, exp_width=300, name_width=380)
    assert out == [300, 412, 0, 588]
    assert sum(out) == sum(sizes)


def test_third_max_extremely_narrow_still_conserves_available_width():
    for total in (250, 400, 600):
        sizes = [100, 100, total - 200]
        out = maximize_with_fixed_exp_and_name(
            sizes, 2, exp_width=320, name_width=420)
        assert sum(out) == total
        assert all(n >= 0 for n in out)


def test_fixed_exp_in_normal_third_pane_allocates_delta_to_list():
    out = resize_with_fixed_exp([600, 450, 450], 300, third_index=2)
    assert out == [300, 750, 450]


def test_corrupted_exp_preferences_do_not_break_layout():
    for bad in (None, 'bad', '-6', '', '0', '200000'):
        assert desired_exp_width(bad, 290) == 290
    assert desired_exp_width(440, 290) == 440


def test_real_browser_address_field_is_a_click_selecting_line_edit():
    source = (ROOT / 'src' / 'launch_web_view.py').read_text('utf-8')
    tree = ast.parse(source)
    widget = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                  and node.name == '_SelectAllAddressLineEdit')
    methods = {node.name for node in widget.body if isinstance(node, ast.FunctionDef)}
    assert {'mousePressEvent', 'mouseReleaseEvent'} <= methods
    assert '_SelectAllAddressLineEdit(self.address_shell)' in source
    assert 'QTimer.singleShot(0, lambda: self.selectAll()' in source
    assert 'self.address.returnPressed.connect(self.open_address)' in source


def test_header_saved_only_when_pointer_is_dragging_and_not_spacer():
    source = (ROOT / 'src' / 'expanded_view.py').read_text('utf-8')
    assert 'not self._middle_header_mouse_down' in source
    assert "action == 'resize' and logical == 4" in source
    assert "event.type() == QEvent.Type.MouseButtonPress" in source
    assert 'workspace_files_exp_desired_width_px' in source
    assert 'self._queue_exp_width_restore()' in source
    assert 'maximize_with_fixed_exp_and_name(' in source


def test_real_exp_resize_reads_desired_px_without_saving_a_window_resize():
    import textwrap
    source = (ROOT / 'src' / 'expanded_view.py').read_text('utf-8')
    cls = next(x for x in ast.parse(source).body
               if isinstance(x, ast.ClassDef) and x.name == 'ExpandedLauncherView')
    functions = {}
    for f in cls.body:
        if (isinstance(f, ast.FunctionDef)
                and f.name in ('_restore_exp_width_after_layout',
                               '_on_files_splitter_user_moved', '_record_exp_handle_width')):
            scope = {}
            exec(textwrap.dedent(ast.get_source_segment(source, f)), scope)
            functions[f.name] = scope[f.name]
    assert len(functions) == 3

    class Settings:
        data = {}
        def setValue(self, key, value): self.data[key] = value
        def sync(self): pass
    class Splitter:
        def __init__(self): self.widths = [540, 1460]
        def sizes(self): return list(self.widths)
        def setSizes(self, x): self.widths = list(x)
        def isVisible(self): return True
    settings = Settings()
    splitter = Splitter()
    view = SimpleNamespace(
        launcher=SimpleNamespace(settings=settings, files_exp_embedded_mode=True,
                                 remote_15_mode=False),
        files_splitter=splitter, _exp_desired_width_px=300,
        _exp_width_restore_scheduled=True, _exp_width_applying=False,
        _preview_layout_restoring=False, _preview_maximized=False,
        _exp_handle_dragging=False, _workspace_mode='files',
        _visible_third_column=lambda: None,
        _queue_third_column_reflow=lambda: None,
        _queue_exp_width_restore=lambda: None)
    functions['_restore_exp_width_after_layout'](view)
    assert splitter.widths == [300, 1700]
    assert not settings.data  # WINDOW RESIZE is not a preference edit!
    splitter.widths = [390, 1610]  # the user drags the Exp/List separator
    functions['_on_files_splitter_user_moved'](view, 390, 1)
    assert view._exp_desired_width_px == 300
    assert not settings.data  # synthetic/non-pointer splitterMoved ignored
    view._exp_handle_dragging = True
    # In this standalone test, the real method references itself via view.
    view._record_exp_handle_width = lambda: functions['_record_exp_handle_width'](view)
    functions['_on_files_splitter_user_moved'](view, 390, 1)
    assert view._exp_desired_width_px == 390
    assert settings.data['workspace_files_exp_desired_width_px'] == 390


def test_browser_address_click_selects_all_but_drag_and_right_click_do_not():
    import textwrap
    from types import SimpleNamespace as NS
    source = (ROOT / 'src' / 'launch_web_view.py').read_text('utf-8')
    cls = next(x for x in ast.parse(source).body
               if isinstance(x, ast.ClassDef) and x.name == '_SelectAllAddressLineEdit')
    statement = ast.get_source_segment(source, cls)

    class FakePoint:
        def __init__(self, x, y=0): self.x = x; self.y = y
        def __sub__(self, other): return FakePoint(self.x - other.x, self.y - other.y)
        def manhattanLength(self): return abs(self.x) + abs(self.y)
    class FakeEvent:
        def __init__(self, button, x): self._button = button; self._x = x
        def button(self): return self._button
        def position(self): return NS(toPoint=lambda: FakePoint(self._x))
    class Base:
        def mousePressEvent(self, event): pass
        def mouseReleaseEvent(self, event): pass
        def hasFocus(self): return True
        def selectAll(self): self.selected += 1
    class Timer:
        @staticmethod
        def singleShot(_interval, fn): fn()
    ns = dict(QLineEdit=Base, QTimer=Timer,
              Qt=NS(MouseButton=NS(LeftButton=1)),
              QApplication=NS(startDragDistance=lambda: 10))
    exec(textwrap.dedent(statement), ns)
    widget = ns['_SelectAllAddressLineEdit']()
    widget.selected = 0
    widget.mousePressEvent(FakeEvent(1, 10))
    widget.mouseReleaseEvent(FakeEvent(1, 12))
    assert widget.selected == 1
    widget.mousePressEvent(FakeEvent(1, 10))
    widget.mouseReleaseEvent(FakeEvent(1, 70))
    assert widget.selected == 1  # dragging to select a substring is intact
    widget.mousePressEvent(FakeEvent(2, 10))
    widget.mouseReleaseEvent(FakeEvent(2, 10))
    assert widget.selected == 1  # context menu behavior is intact
