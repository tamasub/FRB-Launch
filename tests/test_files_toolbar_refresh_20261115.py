"""Qt-free tests for Files toolbar Reload and the shared F5 action.

Execute production methods with lightweight doubles to exercise the actual
state/refresh contract even on CI systems without PySide6 installed.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
EXP = (ROOT / 'src/remote_files_explorer.py').read_text(encoding='utf-8')
APP = (ROOT / 'src/app.py').read_text(encoding='utf-8')


def method(source, class_name, method_name, globals_):
    module = ast.parse(source)
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef)
               and node.name == class_name)
    fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
              and node.name == method_name)
    tree = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    namespace = dict(globals_)
    exec(compile(tree, '<isolated-source>', 'exec'), namespace)
    return namespace[method_name]


QT = NS(State=NS(EditingState=1))


def test_refresh_button_is_to_right_of_up_and_uses_browser_reload_icon():
    assert "self.files_refresh_button.setObjectName('expandedFilesRefresh')" in VIEW
    assert "browser_navigation_icon(\n            'reload', theme_family(self.launcher.color_theme))" in VIEW
    assert 'self.files_refresh_button.clicked.connect(self.refresh_files_view)' in VIEW
    assert VIEW.index('shared_layout.insertWidget(shared_layout.indexOf(self.address_bar), self.middle.back)') < VIEW.index('shared_layout.insertWidget(shared_layout.indexOf(self.address_bar),\n                                   self.files_refresh_button)')
    assert 'QToolButton#expandedFilesRefresh' in VIEW
    assert "self.files_refresh_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)" in VIEW
    assert "self.folder_refresh_shortcut.activated.connect(self.refresh_current_middle_folder)" in APP
    assert 'view.refresh_files_view()' in APP


class Node:
    def __init__(self, path=None, children=(), *, opened=False, pc=False, virtual=False):
        self.path = path
        self.children = list(children)
        self.opened = opened
        self.pc = pc
        self.virtual = virtual

    def rowCount(self): return len(self.children)
    def child(self, i): return self.children[i]
    def index(self): return self
    def data(self, _role):
        return {'path': self.path, 'pc': self.pc,
                'virtual': {'node_id': 'virtual-page'} if self.virtual else None}


def test_exp_reloads_outermost_open_physical_roots_only(tmp_path):
    a, b, c, d = (tmp_path / part for part in ('a', 'b', 'c', 'd'))
    for path in (a, b, c, d): path.mkdir()
    # a/a-child is open; refreshing a handles descendants in one operation.
    achild = a / 'inner'
    achild.mkdir()
    root = Node(children=[
        Node(str(a), [Node(str(achild), opened=True)], opened=True),
        Node(str(b), opened=False),
        Node(children=[Node(str(c), opened=True)], opened=True, virtual=True),
        Node(str(d), opened=False),
    ])
    observed = []
    refresh = method(EXP, 'RemoteFilesExplorer', 'refresh_open_directories',
                     {'os': os, '_DATA_ROLE': object()})
    exp = NS(model=NS(invisibleRootItem=lambda: root),
             tree=NS(isExpanded=lambda node: node.opened),
             refresh_directory_branch=lambda path: (observed.append(path) or True))
    assert refresh(exp) is True
    assert observed == [str(a), str(c)]
    # no HOME, no reset_to_roots, no navigation, no update of authored JSON


def test_files_button_and_f5_refresh_same_view_without_navigation():
    refresh = method(VIEW, 'ExpandedLauncherView', 'refresh_files_view',
                     {'QAbstractItemView': NS(State=QT.State)})
    trace = []
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              middle=NS(tree=NS(state=lambda: 0)),
              embedded_files_exp=NS(refresh_open_directories=lambda: trace.append('exp')),
              _virtual_directory_node=None,
              refresh_current_directory=lambda: (trace.append('list') or True))
    assert refresh(view) is True
    assert trace == ['exp', 'list']
    assert view._in_place_files_refresh is False
    view._workspace_mode = 'browser'
    assert refresh(view) is False
    assert trace == ['exp', 'list']
    view._workspace_mode = 'files'
    view.middle.tree.state = lambda: 1  # Inline rename in progress.
    assert refresh(view) is False
    assert trace == ['exp', 'list']


class Scroll:
    def __init__(self, val): self.pos = val
    def value(self): return self.pos
    def setValue(self, val): self.pos = val


class Row:
    def __init__(self, title, selected=False):
        self.title = title
        self.selected = selected
    def setSelected(self, enabled): self.selected = enabled


class ListTree:
    def __init__(self, names):
        self.rows = [Row(name, selected=name == 'b') for name in names]
        self.current = self.rows[-1]
        self.v = Scroll(48)
        self.h = Scroll(35)
    def state(self): return 0
    def currentItem(self): return self.current
    def selectedItems(self): return [r for r in self.rows if r.selected]
    def topLevelItemCount(self): return len(self.rows)
    def topLevelItem(self, i): return self.rows[i]
    def clearSelection(self):
        for r in self.rows: r.selected = False
    def setCurrentItem(self, row): self.current = row
    def verticalScrollBar(self): return self.v
    def horizontalScrollBar(self): return self.h


def test_virtual_list_refresh_keeps_cursor_selection_and_both_scrollbars():
    refresh = method(VIEW, 'ExpandedLauncherView', 'refresh_files_view',
                     {'QAbstractItemView': NS(State=QT.State)})
    tree = ListTree(['a', 'b'])
    seen = []
    def rerender():
        tree.rows = [Row('b'), Row('new'), Row('a')]
        tree.current = None
        tree.v.pos = tree.h.pos = 0
        seen.append('list')
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              middle=NS(tree=tree),
              embedded_files_exp=NS(refresh_open_directories=lambda: seen.append('exp')),
              _virtual_directory_node={'node_id':'item:page'},
              refresh_middle=rerender,
              row_data=lambda item: {'title':item.title} if item else None)
    assert refresh(view)
    assert seen == ['exp','list']
    assert tree.current.title == 'b'
    assert [r.title for r in tree.selectedItems()] == ['b']
    assert (tree.v.value(), tree.h.value()) == (48,35)
    assert view._in_place_files_refresh is False


def test_no_user_config_or_authored_menu_changes():
    # The button only calls existing read-only refresh routes.
    body = VIEW.split('    def refresh_files_view(', 1)[1].split(
        '    def refresh_current_directory(', 1)[0]
    assert 'self.reset_to_roots(' not in body
    assert 'self.set_roots(' not in body
    assert 'write_text(' not in body
    assert 'save(' not in body


def test_in_place_refresh_suppresses_exp_navigation_sync_and_restores_flag():
    assert "if callable(changed) and not getattr(self, '_in_place_files_refresh', False):" in VIEW
    refresh = method(VIEW, 'ExpandedLauncherView', 'refresh_files_view',
                     {'QAbstractItemView': NS(State=QT.State)})
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              middle=NS(tree=NS(state=lambda: 0)),
              embedded_files_exp=NS(refresh_open_directories=lambda: None),
              _virtual_directory_node=None)
    def raise_error():
        assert view._in_place_files_refresh is True
        raise RuntimeError('simulated unavailable folder')
    view.refresh_current_directory = raise_error
    try:
        refresh(view)
        assert False, 'expected exception'
    except RuntimeError:
        pass
    assert view._in_place_files_refresh is False
