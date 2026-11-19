"""Regression: only explicit registration may create a Files Exp root.

Works headlessly in CI. Windows GUI smoke remains required for click/focus.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from directory_address import normalized_directory, directory_row


def method_source(module, cls_name, method_name):
    tree = ast.parse((ROOT / 'src' / module).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)


def test_every_passive_folder_navigation_disables_direct_root_creation():
    view = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    assert 'lambda path: self.go_to_directory(path),' in view  # breadcrumb Enter + blue arrow
    assert 'lambda path: self.go_to_directory(path, direct_anchor=True),' not in view
    favorites = ast.unparse(method_source('expanded_view.py', 'ExpandedLauncherView', 'directory_favorite_clicked'))
    third = ast.unparse(method_source('expanded_view.py', 'ExpandedLauncherView', '_open_third_column_folder'))
    assert 'self.go_to_directory(path)' in favorites
    assert 'self.go_to_directory(folder)' in third
    assert 'direct_anchor=True' not in favorites + third


def test_typed_folder_navigation_does_not_mark_an_unregistered_exp_root():
    method = method_source('expanded_view.py', 'ExpandedLauncherView', 'go_to_directory')
    cls = ast.ClassDef(name='Headless', bases=[], keywords=[], body=[method], decorator_list=[])
    namespace = dict(normalized_directory=normalized_directory, directory_row=directory_row)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 '<shipping-expanded>', 'exec'), namespace)
    instance = namespace['Headless']()
    instance.launcher = SimpleNamespace(expander=lambda: SimpleNamespace(expand=lambda p: p),
                                        remote_window=None)
    instance.path = []
    instance._virtual_directory_node = None
    instance._filesystem_entry_origin = None
    instance._direct_entry_root = None
    instance._registered_root_origin = None
    instance.middle = object()
    instance.refresh_middle = lambda: None
    instance.focus_panel = lambda _: None
    with patch('os.path.isdir', return_value=True):
        assert instance.go_to_directory(r'C:\Users\test\403_037')
    assert instance._direct_entry_root is None
    assert instance._registered_root_origin is None
    assert instance.path[0]['title'] == '403_037'


def test_clear_direct_roots_only_removes_legacy_transient_rows_without_callbacks():
    method = method_source('remote_files_explorer.py', 'RemoteFilesExplorer', 'clear_direct_roots')
    cls = ast.ClassDef(name='Headless', bases=[], keywords=[], body=[method], decorator_list=[])
    namespace = {'_DATA_ROLE': 99}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 '<shipping-exp>', 'exec'), namespace)
    class Row:
        def __init__(self, payload): self.payload = payload
        def data(self, role):
            assert role == 99
            return self.payload
    class Parent:
        def __init__(self):
            self.rows = [Row({'path': r'F:\authored'}),
                         Row({'path': r'F:\temp1', 'direct_root': True}),
                         Row({'pc': True}),
                         Row({'path': r'F:\temp2', 'direct_root': True})]
        def rowCount(self): return len(self.rows)
        def child(self, index): return self.rows[index]
        def removeRow(self, index): self.rows.pop(index)
    parent = Parent()
    stops, saves = [], []
    exp = namespace['Headless']()
    exp.model = SimpleNamespace(invisibleRootItem=lambda: parent)
    exp._selection_timer = SimpleNamespace(stop=lambda: stops.append(True))
    exp._syncing_directory = False
    exp._schedule_tree_state_save = lambda: saves.append(True)
    assert exp.clear_direct_roots()
    assert [row.payload for row in parent.rows] == [
        {'path': r'F:\authored'}, {'pc': True}]
    assert not exp._syncing_directory
    assert len(stops) == len(saves) == 1
    assert not exp.clear_direct_roots()  # idempotent
    assert len(stops) == len(saves) == 1


def test_both_exp_panels_clear_obsolete_direct_roots_on_normal_navigation():
    view = ast.unparse(method_source('expanded_view.py',
                                    'ExpandedLauncherView', 'align_files_exp_with_location'))
    app = ast.unparse(method_source('app.py', 'Launcher', 'on_files_directory_changed'))
    assert 'if direct is None:\n' in view
    assert 'panel.clear_direct_roots()' in view
    assert 'if direct_root is None:\n' in app
    assert 'exp_panel.clear_direct_roots()' in app
    assert 'ensure_direct_root(' in view + app  # legacy explicit anchors remain supported
