"""Regression: a newly opened Files Exp path must not resurrect old branches.

Production methods extracted with AST, so the behavioral checks run without
Windows/PySide6. Actual Qt rendering still needs a Windows GUI smoke test.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import os

ROOT = Path(__file__).resolve().parents[1]


def method(file, cls, name, scope=None):
    module = ast.parse((ROOT / 'src' / file).read_text(encoding='utf-8'))
    node = next(x for x in module.body if isinstance(x, ast.ClassDef) and x.name == cls)
    fn = next(x for x in node.body if isinstance(x, ast.FunctionDef) and x.name == name)
    ns = dict(scope or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), file, 'exec'), ns)
    return ns[name]


class Index:
    def __init__(self, node=None):
        self.node = node
    def isValid(self):
        return self.node is not None
    def parent(self):
        return Index(self.node.parent) if self.node else Index()
    def __hash__(self):
        return hash(id(self.node))
    def __eq__(self, other):
        return isinstance(other, Index) and self.node is other.node


class Node:
    def __init__(self, name, *children):
        self.name = name
        self.children = list(children)
        self.parent = None
        for child in children:
            child.parent = self
    def index(self):
        return Index(self)


class Model:
    def __init__(self, *roots):
        self.roots = roots
    def rowCount(self, index=None):
        return len(index.node.children) if index is not None and index.isValid() else len(self.roots)
    def index(self, row, col, index=None):
        entries = (index.node.children if index is not None and index.isValid()
                   else self.roots)
        if 0 <= row < len(entries):
            return entries[row].index()
        return Index()


class Tree:
    def __init__(self):
        self.open = set()
        self.current = Index()
        self.operations = []
    def isExpanded(self, index):
        return index.node in self.open
    def expand(self, index):
        self.open.add(index.node)
        self.operations.append(('open', index.node.name))
    def collapse(self, index):
        self.open.discard(index.node)
        self.operations.append(('close', index.node.name))
    def currentIndex(self):
        return self.current
    def setCurrentIndex(self, index):
        self.current = index
        self.operations.append(('select', index.node.name if index.isValid() else None))
    def clear_wheel_pending(self):
        pass
    def clearSelection(self):
        self.operations.append(('clear-selection', None))


def panel(model, tree, legacy=False):
    calls = []
    p = NS(model=model, tree=tree, _syncing_directory=False,
           _restoring_tree=False,
           _selection_timer=NS(stop=lambda: calls.append('stop')),
           _schedule_tree_state_save=lambda: calls.append('save'),
           _launcher=NS(exp_auto_expand=legacy), calls=calls)
    p._collapse_exp_branches_except = lambda keep=None: prune(p, keep)
    return p


prune = method('remote_files_explorer.py', 'RemoteFilesExplorer',
               '_collapse_exp_branches_except', {'QModelIndex': Index})
on_expand = method('remote_files_explorer.py', 'RemoteFilesExplorer',
                   '_collapse_stale_exp_branches')
prepare = method('remote_files_explorer.py', 'RemoteFilesExplorer',
                 'prepare_breadcrumb_expansion', {'QModelIndex': Index})


def test_manual_open_closes_old_path_including_old_hidden_children():
    old_grandchild = Node('old-grandchild')
    old_child = Node('old-child', old_grandchild)
    old_root = Node('old-root', old_child)
    new_child = Node('new-child')
    new_root = Node('new-root', new_child)
    tree = Tree()
    tree.open.update((old_root, old_child, old_grandchild))
    p = panel(Model(old_root, new_root), tree)

    tree.expand(new_root.index())  # The actual human disclosure fires first.
    on_expand(p, new_root.index())
    assert tree.open == {new_root}
    assert tree.operations == [
        ('open', 'new-root'), ('close', 'old-grandchild'),
        ('close', 'old-child'), ('close', 'old-root')]
    assert p._syncing_directory is False

    tree.expand(new_child.index())
    on_expand(p, new_child.index())
    assert tree.open == {new_root, new_child}  # Keep path to new child.

    # Reopen the old root: old nested children must stay folded.
    tree.expand(old_root.index())
    on_expand(p, old_root.index())
    assert tree.open == {old_root}


def test_programmatic_or_legacy_or_restore_does_not_prune():
    left, right = Node('old'), Node('new')
    for legacy, syncing, restoring in ((True, False, False),
                                       (False, True, False),
                                       (False, False, True)):
        tree = Tree()
        tree.open.update((left, right))
        p = panel(Model(left, right), tree, legacy)
        p._syncing_directory = syncing
        p._restoring_tree = restoring
        on_expand(p, right.index())
        assert tree.open == {left, right}


def test_explicit_breadcrumb_action_folds_first_then_selects_target():
    old_child = Node('old-child')
    old_root = Node('old-root', old_child)
    new_child = Node('new-child')
    new_root = Node('new-root', new_child)
    tree = Tree()
    tree.open.update((old_root, old_child))
    tree.current = old_child.index()
    p = panel(Model(old_root, new_root), tree)
    prepare(p)
    assert tree.open == set()
    assert tree.current == Index()  # Important: bypass same-folder fast path.
    assert tree.operations[-2:] == [('clear-selection', None), ('select', None)]
    # The ordinary breadcrumb aligner then opens only the requested path.
    tree.expand(new_root.index())
    tree.setCurrentIndex(new_child.index())
    assert tree.open == {new_root}
    assert tree.current == new_child.index()


def test_command_calls_prepare_before_align_only_in_new_mode():
    events = []
    tree = NS(setFocus=lambda _: events.append('focus'))
    exp = NS(tree=tree, prepare_breadcrumb_expansion=lambda: events.append('fold'))
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              align_files_exp_with_location=lambda panel, expand: events.append('align') or True)
    launcher = NS(expanded_view=view, exp_auto_expand=False,
                  _current_remote_files_exp=lambda: exp,
                  remote_focus_area=lambda _: events.append('remote-focus'))
    action = method('app.py', 'Launcher', 'expand_exp_to_breadcrumb',
                    {'Qt': NS(FocusReason=NS(OtherFocusReason=1))})
    assert action(launcher)
    assert events == ['fold', 'align', 'remote-focus', 'focus']
    launcher.exp_auto_expand = True
    events.clear()
    assert action(launcher)
    assert events == ['align', 'remote-focus', 'focus']


def test_current_folder_is_reopened_after_old_path_was_folded(tmp_path):
    folder = tmp_path / 'A'
    sub = folder / 'B'
    leaf = sub / 'C'
    leaf.mkdir(parents=True)
    other = tmp_path / 'OLD'
    other.mkdir()
    a = Node('A', Node('B', Node('C')))
    old = Node('OLD')
    tree = Tree()
    tree.open.update((a, a.children[0], old))
    tree.current = a.children[0].children[0].index()  # Same current path!
    p = panel(Model(a, old), tree)
    locations = {a: str(folder), a.children[0]: str(sub),
                 a.children[0].children[0]: str(leaf), old: str(other)}
    p.model.itemFromIndex = lambda idx: idx.node
    for node, path in locations.items():
        node.path = path
        node.data = lambda role, node=node: {'path': locations[node], 'pc': False}
        node.text = lambda node=node: node.name
        node.rowCount = lambda node=node: len(node.children)
        node.child = lambda row, node=node: node.children[row]
    p._index_path = lambda idx: locations.get(idx.node)
    p._rename_in_progress = None
    p._expand_index = Mock()
    tree.scrollTo = Mock()
    p._tree_state_timer = NS(stop=lambda: None)

    # Explicit action folds everything, even though target equals old current.
    prepare(p)
    assert not tree.open and tree.current == Index()
    sync = method('remote_files_explorer.py', 'RemoteFilesExplorer',
                  'sync_current_directory', {
                      'os': os, '_DATA_ROLE': 1,
                      'QAbstractItemView': NS(ScrollHint=NS(EnsureVisible=1))})
    assert sync(p, str(leaf), expand=True)
    assert tree.current == a.children[0].children[0].index()
    assert tree.open == {a, a.children[0]}
    assert old not in tree.open


def test_signal_wiring_and_no_unwanted_ini_changes():
    source = (ROOT / 'src/remote_files_explorer.py').read_text(encoding='utf-8')
    assert 'self.tree.expanded.connect(self._collapse_stale_exp_branches)' in source
    assert 'self.tree.collapsed.connect(self._collapse_stale_exp_branches)' not in source
    assert 'exp_auto_expand=false' in (ROOT / 'defaults/state.ini').read_text(encoding='utf-8')
