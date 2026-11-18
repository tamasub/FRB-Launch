"""Exercise real virtual-item context builder with a two-row JSON selection.

A single-item editor must be disabled for a batch, but batch unregister
remains available. No GUI installation is needed for this logic regression.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'app.py'


class Action:
    def __init__(self, name):
        self.name = name
        self.enabled = True
        self.triggered = SimpleNamespace(connect=lambda cb: None)
    def setEnabled(self, value):
        self.enabled = bool(value)
    def setIcon(self, *args):
        pass


class Menu:
    def __init__(self):
        self.rows = []
    def addSection(self, name):
        self.rows.append(Action('section:' + name))
    def addSeparator(self):
        self.rows.append(Action('separator'))
    def addAction(self, name):
        a = Action(name)
        self.rows.append(a)
        return a


def real_builder():
    source = ast.parse(SOURCE.read_text(encoding='utf-8'))
    method = next(m for c in source.body if isinstance(c, ast.ClassDef)
                  for m in c.body if isinstance(m, ast.FunctionDef)
                  and m.name == 'show_virtual_launch_context')
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    namespace = {
        'virtual_studio_target': lambda identity, *args: {
            'kind': 'item', 'page_id': identity['page_id'],
            'item_id': identity['item_id']},
        'context_action_icon': lambda x: x,
        'QTimer': SimpleNamespace(singleShot=lambda *args: None),
        'QApplication': SimpleNamespace(clipboard=lambda: None),
    }
    exec(compile(module, '<virtual-menu>', 'exec'), namespace)
    return namespace['show_virtual_launch_context']


def build_menu(count):
    builder = real_builder()
    selected = [('work', 'a'), ('work', 'b')][:count]
    launcher = SimpleNamespace(
        pages=[], authored_items=[{'page_id': 'work', 'item_id': 'a',
                                   'item_kind': 'command'}],
        _create_files_context_menu=lambda parent: Menu(),
        _selected_launch_json_items=lambda identity: selected,
        hover_timer=SimpleNamespace(stop=lambda: None),
        pending_menu_item=None, expanded_options={},
    )
    return builder(launcher, {'source': 'launch_json', 'page_id': 'work',
                               'item_id': 'a', 'node_id': 'item:work:a'},
                   None, return_menu=True)


def test_multiple_json_rows_disable_single_row_operations_and_keep_batch_removal():
    menu = build_menu(2)
    actions = {a.name: a for a in menu.rows}
    assert not actions['簡易編集...'].enabled
    assert not actions['詳細編集...'].enabled
    assert not actions['JSON参照IDをコピー'].enabled
    assert actions['登録解除（2件）...'].enabled


def test_one_json_row_retains_single_row_operations():
    menu = build_menu(1)
    actions = {a.name: a for a in menu.rows}
    assert actions['簡易編集...'].enabled
    assert actions['詳細編集...'].enabled
    assert actions['JSON参照IDをコピー'].enabled
