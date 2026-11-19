"""2026-11-19: files Enter preview parity and drag/double-click title contract.

Pure logic/AST tests; Windows native drag and embedded HWND need a GUI smoke.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

BASE = Path(__file__).resolve().parents[1] / 'src'
VIEW = (BASE / 'expanded_view.py').read_text(encoding='utf-8')
APP = (BASE / 'app.py').read_text(encoding='utf-8')
DRAG = (BASE / 'passive_header_drag.py').read_text(encoding='utf-8')


def extract(source, klass, method, namespace):
    tree = ast.parse(source)
    group = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == klass)
    node = next(x for x in group.body if isinstance(x, ast.FunctionDef) and x.name == method)
    exec(compile(ast.fix_missing_locations(ast.Module([node], type_ignores=[])), '<extracted>', 'exec'), namespace)
    return namespace[method]


class FakeTree:
    _rename_enter_guard = False
    def state(self): return 'idle'


def run_leaf(method, row, route_result):
    observed = []
    tree = FakeTree()
    middle = NS(tree=tree)
    launcher = NS(activate=lambda r: observed.append('legacy'),
                  activate_virtual_launch_item=lambda r: observed.append('virtual'),
                  execute=lambda r: observed.append('execute'))
    obj = NS(middle=middle, left=object(), right=object(),
             row_data=lambda _: row, launcher=launcher,
             preview_bookmark_from_list=lambda r: observed.append('preview') or route_result)
    function = extract(VIEW, 'ExpandedLauncherView', method, {
        'QAbstractItemView': NS(State=NS(EditingState='editing')),
    })
    function(obj, middle, object())
    return observed


def test_enter_and_activation_both_preview_managed_json_markdown_and_url():
    rows = (
        {'item_kind': 'file', '_browse_file': 'data/_studio_work.json'},
        {'item_kind': 'file', '_browse_file': 'docs/test.md'},
        {'item_kind': 'file', '_launch_virtual_node': {'kind': 'file', 'row': {'title': 'https'}}},
    )
    for row in rows:
        for action in ('enter_row', 'activate_row'):
            assert run_leaf(action, row, True) == ['preview'], (action, row)


def test_fallback_when_not_preview_eligible_still_executes_normally():
    row = {'item_kind': 'file', '_browse_file': 'backup.zip'}
    for action in ('enter_row', 'activate_row'):
        assert run_leaf(action, row, False) == ['preview', 'legacy']


def test_keyboard_enter_keeps_folder_navigation_out_of_preview():
    called = []
    tree = FakeTree()
    middle = NS(tree=tree)
    obj = NS(middle=middle, left=object(), row_data=lambda _: {'item_kind': 'directory'},
             preview_bookmark_from_list=lambda row: called.append('preview') or True,
             navigate_middle=lambda row: called.append('navigate'),
             launcher=NS(activate=lambda row: called.append('legacy')))
    fn = extract(VIEW, 'ExpandedLauncherView', 'enter_row', {'QAbstractItemView': NS(State=NS(EditingState='editing'))})
    fn(obj, middle, object())
    assert called == ['navigate']


def test_rename_editor_enter_is_never_preview():
    called = []
    tree = FakeTree()
    tree._rename_enter_guard = True
    middle = NS(tree=tree)
    obj = NS(middle=middle, row_data=lambda _: {'item_kind': 'file'},
             preview_bookmark_from_list=lambda row: called.append('preview') or True)
    for name in ('enter_row', 'activate_row'):
        extract(VIEW, 'ExpandedLauncherView', name, {'QAbstractItemView': NS(State=NS(EditingState='editing'))})(obj, middle, object())
    assert not called


def test_launch_then_third_maximization_precedence():
    calls = []
    maximized = {'value': False}
    preview = NS(toggle_third_column_maximize=lambda: calls.append('third'))
    view = NS(isVisible=lambda: True, toggle_third_column_maximize=preview.toggle_third_column_maximize)
    window = NS(isMaximized=lambda: maximized['value'],
                windowState=lambda: 0,
                expanded_view=view,
                toggle_maximize_restore=lambda: (calls.append('window'), maximized.update(value=True)))
    Qt = NS(WindowState=NS(WindowMaximized=2))
    fn = extract(APP, 'Launcher', 'maximize_launch_then_third', {'Qt': Qt})
    fn(window)
    fn(window)
    fn(window)
    assert calls == ['window', 'third', 'third']


def test_all_header_surfaces_are_registered_without_active_controls():
    for s in ("surface.setProperty('frbHeaderDoubleClick', 'window')",
              'self.brand_icon_label, self.brand_title_label',
              "self._install_launch_header_drag('window', self.files_list_title_box",
              "self._install_launch_header_drag('window', self.shared_header",
              "self._install_launch_header_drag('window', exp_header",
              "self._install_launch_header_drag('third', panel.header",
              "self._install_launch_header_drag('third', self.studio_preview.header"):
        assert s in (APP + VIEW), s
    assert "self.search.setProperty('frbHeaderDoubleClick'" not in APP
    assert "self.address_bar.setProperty('frbHeaderDoubleClick'" not in VIEW
    assert "self.maximize_button.setProperty('frbHeaderDoubleClick'" not in APP


class FakeQObject:
    def __init__(self, parent=None): pass

class Pt:
    def __init__(self, x, y): self._x, self._y = x, y
    def x(self): return self._x
    def y(self): return self._y
    def __add__(self, p): return Pt(self.x() + p.x(), self.y() + p.y())
    def __sub__(self, p): return Pt(self.x() - p.x(), self.y() - p.y())
    def __eq__(self, p): return (self.x(), self.y()) == (p.x(), p.y())

class FakeEvent:
    def __init__(self, kind, x=0, y=0, buttons=1):
        self.kind, self.point, self.buttons_val = kind, Pt(x, y), buttons
        self.accepted = False
    def type(self): return self.kind
    def button(self): return 1
    def buttons(self): return self.buttons_val
    def globalPosition(self): return NS(toPoint=lambda: self.point)
    def accept(self): self.accepted = True

class FakeWindow:
    def __init__(self): self.moves = []; self.calls = []
    def pos(self): return Pt(10, 10)
    def windowHandle(self): return NS(startSystemMove=lambda: self.calls.append('systemMove') or True)
    def move(self, p): self.moves.append(p)
    def toggle_maximize_restore(self): self.calls.append('windowMax')
    def maximize_launch_then_third(self): self.calls.append('windowThenThird')


def make_filter(window):
    cls = next(node for node in ast.parse(DRAG).body if isinstance(node, ast.ClassDef) and node.name == 'PassiveHeaderDrag')
    namespace = {'QObject': FakeQObject,
                 'QEvent': NS(Type=NS(MouseButtonPress=1, MouseMove=2, MouseButtonRelease=3, MouseButtonDblClick=4)),
                 'Qt': NS(MouseButton=NS(LeftButton=1))}
    exec(compile(ast.fix_missing_locations(ast.Module([cls], type_ignores=[])), '<filter>', 'exec'), namespace)
    return namespace['PassiveHeaderDrag'](window)


def test_window_title_doubleclick_does_not_start_system_drag():
    win = FakeWindow(); drag = make_filter(win)
    widget = NS(objectName=lambda: 'brandTitleLabel', property=lambda name: 'window')
    assert drag.eventFilter(widget, FakeEvent(1, 12, 13))
    assert win.calls == []
    assert drag.eventFilter(widget, FakeEvent(3, 12, 13, buttons=0))
    assert drag.eventFilter(widget, FakeEvent(4, 12, 13))
    assert win.calls == ['windowMax']


def test_third_title_doubleclick_and_drag_are_distinct():
    win = FakeWindow(); drag = make_filter(win)
    widget = NS(objectName=lambda: 'filesStudioPreviewTitle', property=lambda name: 'third')
    assert drag.eventFilter(widget, FakeEvent(1, 12, 13))
    assert drag.eventFilter(widget, FakeEvent(4, 12, 13))
    assert win.calls == ['windowThenThird']
    assert drag.eventFilter(widget, FakeEvent(1, 20, 20))
    assert drag.eventFilter(widget, FakeEvent(2, 28, 20))
    assert win.calls == ['windowThenThird', 'systemMove']


def test_unregistered_widgets_are_not_repurposed_for_doubleclick():
    win = FakeWindow(); drag = make_filter(win)
    widget = NS(objectName=lambda: 'nativeHeaderButton', property=lambda name: None)
    assert not drag.eventFilter(widget, FakeEvent(4))
    assert win.calls == []
