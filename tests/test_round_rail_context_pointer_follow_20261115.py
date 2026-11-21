"""丸レール／列切替メニュー: 自動移動の実行モデル回帰。PySide6不要。"""
import ast
from pathlib import Path
from types import MethodType, SimpleNamespace as NS

SRC = Path(__file__).resolve().parents[1] / 'src'
APP = (SRC / 'app.py').read_text(encoding='utf-8')
VIEW = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
PAD = (SRC / 'launch_remote.py').read_text(encoding='utf-8')


def _source_method(code, cls, name):
    tree = ast.parse(code)
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)


class Cursor:
    current = (20, 20)
    moves = []

    @classmethod
    def pos(cls):
        return cls.current

    @classmethod
    def setPos(cls, p):
        cls.current = p
        cls.moves.append(p)


class Rectangle:
    def __init__(self, left=10, top=20, width=200, height=22):
        self.l, self.t, self.w, self.h = left, top, width, height

    def intersected(self, other):
        return self

    def isValid(self):
        return self.w > 0 and self.h > 0

    def isEmpty(self):
        return not self.isValid()

    def left(self):
        return self.l

    def width(self):
        return self.w

    def center(self):
        return NS(y=lambda: self.t + self.h // 2)


class Tree:
    def __init__(self, *, index=True, item=True, offset=100):
        self.index, self.item, self.offset = index, item, offset
        self.scrolled = []
        self.focus_reasons = []

    def setFocus(self, reason):
        self.focus_reasons.append(reason)

    def isVisible(self):
        return True

    def currentIndex(self):
        return NS(isValid=lambda: self.index)

    def currentItem(self):
        return object() if self.item else None

    def scrollTo(self, item, hint):
        self.scrolled.append(('exp', item))

    def scrollToItem(self, item, hint):
        self.scrolled.append(('list', item))

    def visualRect(self, item):
        return Rectangle()

    def visualItemRect(self, item):
        return Rectangle()

    def viewport(self):
        return NS(rect=lambda: Rectangle(0, 0, 300, 800),
                  mapToGlobal=lambda point: (point[0] + self.offset, point[1]))


def _launcher(pointer_warp_enabled=True, index=True, item=True):
    Cursor.current = (20, 20)
    Cursor.moves = []
    exp_tree = Tree(index=index, offset=100)
    list_tree = Tree(item=item, offset=500)
    view = NS(isVisible=lambda: True, _workspace_mode='files', middle=NS(tree=list_tree))
    calls, jobs = [], []
    context = {
        'QCursor': Cursor,
        'QTimer': NS(singleShot=lambda ms, fn: jobs.append(fn)),
        'QApplication': NS(mouseButtons=lambda: 0),
        'Qt': NS(MouseButton=NS(NoButton=0), FocusReason=NS(ShortcutFocusReason=19)),
        'QAbstractItemView': NS(ScrollHint=NS(EnsureVisible=1)),
        'QPoint': lambda x, y: (x, y),
    }
    funcs = [_source_method(APP, 'Launcher', n) for n in
             ('_dispatch_files_column_context_navigation', '_follow_files_column_context_pointer')]
    ns = dict(context)
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                 str(SRC / 'app.py'), 'exec'), ns)
    launcher = NS(
        pointer_warp_enabled=pointer_warp_enabled,
        _remote_context_wheel=None,
        _files_operating_target='files_exp',
        expanded_view=view,
        _current_remote_files_exp=lambda: NS(tree=exp_tree, isWindow=lambda:False),
    )
    def focus(target):
        calls.append(target)
        launcher._files_operating_target = target
    launcher.remote_focus_area = focus
    for name in ('_dispatch_files_column_context_navigation', '_follow_files_column_context_pointer'):
        setattr(launcher, name, MethodType(ns[name], launcher))
    def drain():
        while jobs:
            jobs.pop(0)()
    menu = NS(close=lambda: calls.append('close'))
    return launcher, menu, calls, drain, exp_tree, list_tree


def test_menu_follow_exp_current_row_on():
    owner, menu, calls, drain, exp, lst = _launcher(True)
    owner._dispatch_files_column_context_navigation(menu, 'files_exp')
    drain()
    assert calls == ['close', 'files_exp']
    assert exp.scrolled and not lst.scrolled
    assert Cursor.moves == [(180, 31)]


def test_menu_follow_list_current_row_on():
    owner, menu, calls, drain, exp, lst = _launcher(True)
    owner._dispatch_files_column_context_navigation(menu, 'directory')
    drain()
    assert calls == ['close', 'directory']
    assert lst.scrolled and not exp.scrolled
    assert Cursor.moves == [(580, 31)]


def test_menu_pointer_off_keeps_mouse_where_human_left_it():
    owner, menu, calls, drain, exp, lst = _launcher(False)
    owner._dispatch_files_column_context_navigation(menu, 'directory')
    drain()
    assert calls == ['close', 'directory']
    assert not Cursor.moves and Cursor.pos() == (20, 20)
    assert not exp.scrolled and not lst.scrolled


def test_user_mouse_move_after_menu_wins_over_delayed_warp():
    owner, menu, calls, drain, exp, lst = _launcher(True)
    owner._dispatch_files_column_context_navigation(menu, 'directory')
    Cursor.current = (77, 88)
    drain()
    assert calls == ['close', 'directory']
    assert not Cursor.moves and Cursor.pos() == (77, 88)


def test_no_existing_exp_row_does_not_invent_a_destination():
    owner, menu, calls, drain, exp, lst = _launcher(True, index=False)
    owner._dispatch_files_column_context_navigation(menu, 'files_exp')
    drain()
    assert not Cursor.moves


def test_no_existing_list_row_does_not_invent_a_destination():
    owner, menu, calls, drain, exp, lst = _launcher(True, item=False)
    owner._dispatch_files_column_context_navigation(menu, 'directory')
    drain()
    assert not Cursor.moves


def test_round_doubleclick_no_warp_off_and_release_only_on():
    command = _source_method(VIEW, 'ExpandedLauncherView', 'rail_wheel_command')
    body = ast.get_source_segment(VIEW, command)
    assert "if not getattr(self.launcher, 'pointer_warp_enabled', True):" in body
    assert 'pending_click.stop()' in body
    assert 'self.launcher.remote_command(command)' in body
    assert '_warp_rail_pointer_to_list)' not in body, 'カーソルは押下中には飛ばさない'
    assert 'self.rail_wheel.double_click_released.connect(' in VIEW
    assert 'lambda: QTimer.singleShot(0, self._warp_rail_pointer_to_list)' in VIEW
    assert 'self.double_click_released.emit()' in PAD
    assert 'or QApplication.mouseButtons() != Qt.MouseButton.NoButton' in VIEW


def test_paint_pointf_fix_and_guaranteed_painter_end():
    imports = [n for n in ast.parse(PAD).body if isinstance(n, ast.ImportFrom)
               and n.module == 'PySide6.QtCore']
    assert any(x.name == 'QPointF' for imp in imports for x in imp.names)
    paint = _source_method(PAD, 'RoundRailWheelPad', 'paintEvent')
    assert any(isinstance(x, ast.Try) and x.finalbody for x in ast.walk(paint))


def test_second_release_must_not_reset_exp_to_list_target_before_warp():
    release = _source_method(PAD, 'RoundRailWheelPad', 'mouseReleaseEvent')
    source = ast.get_source_segment(PAD, release)
    assert 'if not double_release:\n            self._side_from_event(event)' in source
    assert 'self.double_click_released.emit()' in source
