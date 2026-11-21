"""New standard: breadcrumb navigation never automatically opens Exp.

These tests extract production methods with AST: no Windows/PySide6 dependency.
"""
import ast
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from launch_state_defaults import ensure_initial_state_ini
from context_menu_config import load_context_menus


def method(filename, class_name, method_name, namespace):
    tree = ast.parse((ROOT / 'src' / filename).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == class_name)
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == method_name)
    isolated = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(isolated, filename, 'exec'), namespace)
    return namespace[method_name]


def test_release_flags_seeded_from_defaults_and_preserve_existing_appdata(tmp_path):
    text = (ROOT / 'defaults/state.ini').read_text(encoding='utf-8')
    assert 'exp_auto_expand=false' in text
    dest = tmp_path / 'state.ini'
    ensure_initial_state_ini(ROOT / 'defaults/state.ini', dest)
    assert 'exp_auto_expand=false' in dest.read_text(encoding='utf-8')
    dest.write_bytes(b'[General]\r\nexp_auto_expand=true\r\n')
    ensure_initial_state_ini(ROOT / 'defaults/state.ini', dest)
    assert dest.read_bytes() == b'[General]\r\nexp_auto_expand=true\r\n'
    app = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    assert "self.settings.value(\n            'exp_auto_expand', 'false')" in app


def test_context_action_is_right_after_refresh_and_only_list_uses_it():
    config = load_context_menus(ROOT / 'config/context_menu_options.json')
    folder = [x.get('action_id', '|') for x in config['folder']]
    assert folder[folder.index('refresh_directory') + 1] == 'expand_exp_to_breadcrumb'
    assert 'expand_exp_to_breadcrumb' not in [x.get('action_id') for x in config['file']]
    app = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    assert 'if not list_context or search_result:' in app
    assert 'if remote_folder_list:  # Exp/Remote menu is not a List command.' in app
    assert "if getattr(self, 'exp_auto_expand', True):\n            align(panel)" in app
    assert "if ascending_one_level and getattr(self, 'exp_auto_expand', True):" in app


class Index:
    def __init__(self, item=None):
        self.item = item
    def isValid(self):
        return self.item is not None


class Item:
    def __init__(self, path, children=()):
        self.path = str(path)
        self.name = Path(path).name
        self.children = list(children)
        self.idx = Index(self)
    def data(self, _role):
        return {'path': self.path, 'pc': False}
    def index(self):
        return self.idx
    def rowCount(self):
        return len(self.children)
    def child(self, row):
        return self.children[row]
    def text(self):
        return self.name


class Model:
    def __init__(self, top):
        self.top = top
    def rowCount(self):
        return 1
    def index(self, row, col):
        return self.top.index()
    def itemFromIndex(self, index):
        return index.item if index.isValid() else None


class Tree:
    def __init__(self):
        self.current = Index()
        self.expanded = set()
        self.expansions = []
        self.scrolled = []
    def currentIndex(self):
        return self.current
    def setCurrentIndex(self, index):
        self.current = index
    def isExpanded(self, index):
        return index.item.path in self.expanded
    def expand(self, index):
        self.expanded.add(index.item.path)
        self.expansions.append(index.item.path)
    def scrollTo(self, index, *args):
        self.scrolled.append(index.item.path)
    def clear_wheel_pending(self):
        pass


def test_deepest_existing_branch_without_autoexpansion(tmp_path):
    a = tmp_path / 'A'
    b = a / 'B'
    c = b / 'C'
    c.mkdir(parents=True)
    node_c = Item(c)
    node_b = Item(b, [node_c])
    node_a = Item(a, [node_b])
    tree = Tree()
    panel = NS(tree=tree, model=Model(node_a), _rename_in_progress=None,
               _selection_timer=NS(stop=lambda: None), _syncing_directory=False,
               _schedule_tree_state_save=Mock(),
               _index_path=lambda idx: idx.item.path if idx.isValid() else None,
               _expand_index=Mock())
    scope = {'os': os, '_DATA_ROLE': 1,
             'QAbstractItemView': NS(ScrollHint=NS(EnsureVisible=1))}
    sync = method('remote_files_explorer.py', 'RemoteFilesExplorer',
                  'sync_current_directory', scope)
    assert sync(panel, str(c), expand=False)
    assert tree.current.item.path == str(a)
    assert tree.expansions == []
    tree.expand(node_a.index())  # Human opened A
    assert sync(panel, str(c), expand=False)
    assert tree.current.item.path == str(b)
    assert tree.expansions == [str(a)]
    tree.expand(node_b.index())  # Human opened B
    assert sync(panel, str(c), expand=False)
    assert tree.current.item.path == str(c)
    assert tree.expansions == [str(a), str(b)]


def test_legacy_expands_full_path(tmp_path):
    a = tmp_path / 'A'
    b = a / 'B'
    c = b / 'C'
    c.mkdir(parents=True)
    tree = Tree()
    panel = NS(tree=tree, model=Model(Item(a, [Item(b, [Item(c)])])),
               _rename_in_progress=None,
               _selection_timer=NS(stop=lambda: None), _syncing_directory=False,
               _schedule_tree_state_save=Mock(),
               _index_path=lambda idx: idx.item.path if idx.isValid() else None,
               _expand_index=Mock())
    fn = method('remote_files_explorer.py', 'RemoteFilesExplorer',
                'sync_current_directory', {'os': os, '_DATA_ROLE': 1,
                   'QAbstractItemView': NS(ScrollHint=NS(EnsureVisible=1))})
    assert fn(panel, str(c), expand=True)
    assert tree.expansions == [str(a), str(b)]
    assert tree.current.item.path == str(c)


def test_disclosure_does_not_navigate_breadcrumb_in_new_mode(tmp_path):
    a = tmp_path / 'A'
    b = tmp_path / 'B'
    a.mkdir(); b.mkdir()
    index = Index(Item(a))
    operations = []
    view = NS(_workspace_mode='files', current_directory=lambda: str(a/'Nested'),
              align_files_exp_with_location=lambda *args, **kw: operations.append(('align', kw)))
    launcher = NS(exp_auto_expand=False, expanded_view=view,
                  set_files_operating_target=lambda target: operations.append(('focus', target)))
    tree = Tree()
    panel = NS(_syncing_directory=False, _selection_timer=NS(stop=lambda: None),
               tree=tree, _launcher=launcher,
               _index_path=lambda ix: ix.item.path,
               remote_current_virtual_node=lambda: None,
               _activate_index=lambda ix: operations.append(('navigate', ix)))
    fn = method('remote_files_explorer.py', 'RemoteFilesExplorer',
                '_activate_disclosure', {'os': os})
    fn(panel, index)
    assert operations == [('align', {'expand': False}), ('focus', 'files_exp')]
    operations.clear()
    fn(panel, Index(Item(b)))
    assert operations == [('focus', 'files_exp')]  # Unrelated branch stays selected
    launcher.exp_auto_expand = True
    operations.clear()
    panel.remote_current_virtual_node = lambda: None
    fn(panel, index)
    assert operations == [('navigate', index)]  # Legacy route untouched


def test_menu_action_focuses_exp_and_does_not_navigate_list():
    result = []
    panel = NS(tree=NS(setFocus=lambda reason: result.append('native_focus')))
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              align_files_exp_with_location=lambda p, expand: result.append(expand) or True)
    launcher = NS(expanded_view=view, _current_remote_files_exp=lambda: panel,
                  remote_focus_area=lambda area: result.append(area))
    method_fn = method('app.py', 'Launcher', 'expand_exp_to_breadcrumb',
                       {'Qt': NS(FocusReason=NS(OtherFocusReason='qt'))})
    assert method_fn(launcher) is True
    assert result == [True, 'files_exp', 'native_focus']


def test_folder_transition_never_opens_exp_by_default_and_legacy_does():
    import ntpath
    source_panel = NS(isVisible=lambda: True,
                      sync_current_directory=Mock(return_value=True),
                      remote_select_mounted_directory=Mock(return_value=True),
                      collapse_departed_child=Mock(), clear_direct_roots=Mock())
    view = NS(_workspace_mode='files', _filesystem_entry_origin=None,
              _direct_entry_root=None, _registered_root_origin=None,
              embedded_files_exp=source_panel)
    launcher = NS(exp_auto_expand=False, expanded_view=view,
                  remote_window=NS(files_exp_panel=None),
                  _last_files_breadcrumb_directory=r'F:\FRB\A\B',
                  _remote_folder_opener=None, _remote_folder_root_menu=None,
                  refresh_main_files_cut_visuals=Mock(),
                  sync_files_first_column_root=Mock())
    fn = method('app.py', 'Launcher', 'on_files_directory_changed',
                {'ntpath': ntpath, 'os': os})
    fn(launcher, r'F:\FRB\A')
    source_panel.sync_current_directory.assert_not_called()
    source_panel.collapse_departed_child.assert_not_called()
    launcher.refresh_main_files_cut_visuals.assert_called_once()
    launcher.exp_auto_expand = True
    launcher._last_files_breadcrumb_directory = r'F:\FRB\A\B'
    fn(launcher, r'F:\FRB\A')
    source_panel.sync_current_directory.assert_called_once_with(r'F:\FRB\A')
    source_panel.collapse_departed_child.assert_called_once_with(
        r'F:\FRB\A\B', r'F:\FRB\A')


def test_virtual_breadcrumb_stops_at_closed_ancestor_then_advances():
    virtual_a = {'source': 'launch_json', 'node_id': 'a', 'lineage': ['a']}
    virtual_b = {'source': 'launch_json', 'node_id': 'b', 'lineage': ['a', 'b']}
    virtual_c = {'source': 'launch_json', 'node_id': 'c', 'lineage': ['a', 'b', 'c']}
    class VItem(Item):
        def __init__(self, virtual, children=()):
            super().__init__(virtual['node_id'], children)
            self.virtual = virtual
        def data(self, _role):
            return {'virtual': self.virtual}
    class VModel(Model):
        def rowCount(self, parent=None):
            return 1 if parent is None or not parent.isValid() else parent.item.rowCount()
        def index(self, row, column, parent=None):
            return (self.top if parent is None or not parent.isValid()
                    else parent.item.children[row]).index()
    c, b = VItem(virtual_c), None
    b = VItem(virtual_b, [c])
    a = VItem(virtual_a, [b])
    tree = Tree()
    panel = NS(tree=tree, model=VModel(a),
               _syncing_directory=False, _restoring_tree=False,
               _selection_timer=NS(stop=lambda: None),
               _schedule_tree_state_save=Mock())
    fn = method('remote_files_explorer.py', 'RemoteFilesExplorer',
                'remote_select_virtual_node', {'QModelIndex': Index, '_DATA_ROLE': 1,
                 'QAbstractItemView': NS(ScrollHint=NS(EnsureVisible=1))})
    assert fn(panel, virtual_c, expand=False)
    assert tree.current.item.virtual['node_id'] == 'a'
    assert tree.expansions == []
    tree.expand(a.index())
    assert fn(panel, virtual_c, expand=False)
    assert tree.current.item.virtual['node_id'] == 'b'
    assert fn(panel, virtual_c, expand=True)
    assert tree.current.item.virtual['node_id'] == 'c'
    assert tree.expansions == ['a', 'b']
