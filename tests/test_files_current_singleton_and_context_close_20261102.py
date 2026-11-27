"""Files current-row contract and completed-context closure, without Qt runtime."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from paste_destination import choose_paste_destination
from middle_selection_guard import repair_middle_selection

SOURCE_VIEW = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
SOURCE_APP = (ROOT / 'src/app.py').read_text(encoding='utf-8')


def extract(source, owner, name, globals_):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[method], type_ignores=[])
    env = dict(globals_)
    exec(compile(ast.fix_missing_locations(module), '<source>', 'exec'), env)
    return env[name]


class Row:
    def __init__(self, name, selected=False):
        self.data = {'item_id': name}
        self.selected = selected
    def isSelected(self): return self.selected
    def setSelected(self, flag): self.selected = flag


class Tree:
    def __init__(self, rows, current=None):
        self.rows, self.current = rows, current
        self.deliberate_blank_selection = False
        self.focused = False
        self.repaint_count = 0
        self.blank_clicked = None
    def selectionMode(self): return 'extended'
    def itemAt(self, position): return self.rows[0] if position == 'row' else None
    def clearSelection(self):
        for row in self.rows: row.selected = False
    def setFocus(self, reason): self.focused = True
    def viewport(self): return self
    def update(self): self.repaint_count += 1
    def currentItem(self): return self.current
    def setCurrentItem(self, item):
        self.current = item
        item.selected = True
    def selectedItems(self): return [x for x in self.rows if x.selected]
    def topLevelItemCount(self): return len(self.rows)
    def topLevelItem(self, i): return self.rows[i]
    def state(self): return 'idle'
    def scrollToItem(self, item): pass


def test_blank_click_remembers_outline_but_does_not_select_a_paste_target(tmp_path):
    class Base(Tree):
        def mousePressEvent(self, event):
            if self.itemAt(event.position().toPoint()) is not None:
                self.setCurrentItem(self.itemAt('row'))
    view_ast = ast.parse(SOURCE_VIEW)
    source_cls = next(n for n in view_ast.body if isinstance(n, ast.ClassDef)
                      and n.name == '_SeparatedFileTree')
    method = next(n for n in source_cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'mousePressEvent')
    generated = ast.ClassDef(name='_SeparatedFileTree', bases=[ast.Name(id='ExternalFileDragTree', ctx=ast.Load())],
                             keywords=[], body=[method], decorator_list=[])
    env = {'ExternalFileDragTree': Base,
           'QAbstractItemView': NS(SelectionMode=NS(ExtendedSelection='extended')),
           'Qt': NS(MouseButton=NS(LeftButton='left', RightButton='right'),
                    KeyboardModifier=NS(NoModifier='none'),
                    FocusReason=NS(MouseFocusReason='mouse'))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[generated], type_ignores=[])),
                 '<tree>', 'exec'), env)
    a = Row('first', selected=True)
    panel = env['_SeparatedFileTree']([a], a)
    signals = []
    panel.blank_clicked = lambda: signals.append('middle-active')
    event = NS(button=lambda: 'left', modifiers=lambda: 'none',
               position=lambda: NS(toPoint=lambda: 'blank'),
               accept=lambda: signals.append('accepted'))
    panel.mousePressEvent(event)
    assert panel.currentItem() is a  # passive green outline remains
    assert panel.selectedItems() == []  # no active green background
    assert panel.deliberate_blank_selection
    assert signals == ['middle-active', 'accepted']
    folder = tmp_path / 'folder'; folder.mkdir()
    assert choose_paste_destination(folder, panel.selectedItems()) == folder


def test_queued_repair_never_reselects_intentional_blank():
    method = extract(SOURCE_VIEW, 'ExpandedLauncherView', 'ensure_middle_current_selection', {
        'QAbstractItemView': NS(State=NS(EditingState='editing')),
        'repair_middle_selection': repair_middle_selection,
        'row_key': lambda row: row['item_id'] if row else None})
    first = Row('first')
    tree = Tree([first], first)
    tree.deliberate_blank_selection = True
    owner = NS(middle=NS(tree=tree), _middle_selection_repair_running=False,
               _middle_selection_is_active=lambda: True,
               current_directory=lambda: 'root',
               _middle_current_memory=None, row_data=lambda row: row.data)
    assert method(owner) is None
    assert not first.selected
    tree.deliberate_blank_selection = False
    assert method(owner) is first
    assert first.selected


def test_style_inactive_row_is_outline_only_without_green_fill():
    assert 'QTreeWidget#expandedTree[remoteInactive="true"]::item:selected {{background:transparent' in SOURCE_VIEW
    assert 'self.indexOfTopLevelItem(current) == index.row()' in SOURCE_VIEW
    assert "pane.tree.setProperty('remoteInactive', area_name != active_files_area)" in SOURCE_APP
    assert 'self.middle.tree.blank_clicked' in SOURCE_VIEW


def test_finished_action_dismisses_popup_but_navigation_does_not():
    from menu_lifecycle import is_terminal
    from test_menu_lifecycle_processing_20261127 import Action, Menu
    root = Menu('root', [])
    folder_list = Action()
    root.folder_list_action = folder_list
    assert not is_terminal(root, folder_list)
    assert not is_terminal(root, Action(child=Menu('new', [])))
    # New/rename/paste are terminal selections; no caption-specific rules.
    for name in ('新しいフォルダー', '名前の変更', '貼り付け'):
        action = Action()
        action.text = lambda: name
        assert is_terminal(root, action)


def test_explicit_folder_paste_dispatch_has_no_late_global_close():
    calls = []
    dispatch = extract(SOURCE_APP, 'Launcher', '_paste_from_context_menu', {})
    owner = NS(_paste_context_destination=lambda parent:'expanded',
               paste_into_expanded_directory=lambda **kw: calls.append(('paste',kw)))
    dispatch(owner, object(), target_folder='F:/target')
    assert calls == [('paste', {'destination_override':'F:/target'})]
