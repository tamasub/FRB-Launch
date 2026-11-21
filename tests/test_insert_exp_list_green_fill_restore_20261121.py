"""Insert -> List menu 'Exp列へ戻る' -> Exp RIGHT -> List selected fill.

Qt-free state-transition regression using the real methods from the current
source; in particular the previous currentItem is NOT a selected child.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'src/app.py').read_text(encoding='utf-8')
VIEW = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')


def actual(source, cls, name, extra=None):
    klass = next(n for n in ast.parse(source).body
                 if isinstance(n, ast.ClassDef) and n.name == cls)
    node = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)
    env = dict(extra or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<source>', 'exec'), env)
    return env[name]


RESTORE = actual(VIEW, 'ExpandedLauncherView',
                 'restore_middle_first_row_after_folder_operation')
EXP_RIGHT = actual(APP, 'Launcher', 'remote_exp_right_to_list')


class Item:
    def __init__(self, name):
        self.name = name
        self.selected = False

    def isSelected(self):
        return self.selected

    def setSelected(self, value):
        self.selected = value


class Tree:
    def __init__(self, names=('first', 'second'), blank=True):
        self.items = [Item(n) for n in names]
        self.current = self.items[-1] if self.items else None
        self.deliberate_blank_selection = blank
        self._frb_shift_anchor = 'old'
        self.moves = []
        self.viewport_object = NS(update=Mock())

    def topLevelItemCount(self):
        return len(self.items)

    def topLevelItem(self, i):
        return self.items[i]

    def clearSelection(self):
        for item in self.items:
            item.setSelected(False)

    def currentItem(self):
        return self.current

    def setCurrentItem(self, item):
        self.current = item

    def scrollToItem(self, item):
        self.moves.append(item.name)

    def viewport(self):
        return self.viewport_object

    def selectedItems(self):
        return [item for item in self.items if item.isSelected()]


def make_view(tree):
    view = NS(middle=NS(tree=tree), row_data=lambda item: {'path': item.name},
              _queue_files_selection_status=Mock())
    view.restore_middle_first_row_after_folder_operation = lambda: RESTORE(view)
    return view


def make_launcher(view):
    panel = NS(remote_current_folder_path=lambda: 'F:/FRB',
               _selection_timer=NS(stop=Mock()),
               tree=NS(currentIndex=lambda: object()))
    view.isVisible = lambda: True
    view._workspace_mode = 'files'
    view.current_directory = lambda: 'F:/FRB'
    view.expanded_files = panel
    return NS(expanded_view=view, _current_remote_files_exp=lambda: panel,
              navigate_files_exp_folder=Mock(), remote_focus_area=Mock()), panel


def test_full_sequence_insert_menu_exp_then_right_restores_first_selected_green():
    tree = Tree()
    view = make_view(tree)
    launcher, panel = make_launcher(view)
    # Menu return from List to Exp retains Insert's deliberately empty selection.
    queued = []
    menu_dispatch = actual(APP, 'Launcher', '_dispatch_files_column_context_navigation',
                           {'QTimer': NS(singleShot=lambda _ms, fn: queued.append(fn)),
                            'Qt': NS(FocusReason=NS(ShortcutFocusReason=1))})
    panel.tree.isVisible = lambda: True
    panel.tree.setFocus = Mock()
    panel.isWindow = lambda: False
    launcher._remote_context_wheel = None
    launcher.pointer_warp_enabled = False
    menu = NS(close=Mock())
    menu_dispatch(launcher, menu, 'files_exp')
    assert tree.deliberate_blank_selection
    assert tree.selectedItems() == []
    queued.pop(0)()
    launcher.remote_focus_area.assert_called_with('files_exp')
    # Same-folder Exp RIGHT skips the costly List reload; must still select.
    assert EXP_RIGHT(launcher) is True
    assert launcher.navigate_files_exp_folder.call_count == 0
    assert tree.currentItem() is tree.items[0]
    assert tree.items[0].isSelected() is True  # Native green fill.
    assert tree.items[1].isSelected() is False
    assert not tree.deliberate_blank_selection
    assert tree._frb_shift_anchor is None
    assert tree.moves == ['first']
    launcher.remote_focus_area.assert_called_with('directory')
    view._queue_files_selection_status.assert_called_once()


def test_normal_multi_selection_and_current_remain_unchanged():
    tree = Tree(blank=False)
    tree.items[0].setSelected(True)
    tree.items[1].setSelected(True)
    view = make_view(tree)
    launcher, _panel = make_launcher(view)
    assert EXP_RIGHT(launcher) is True
    assert tree.currentItem() is tree.items[1]
    assert tree.selectedItems() == tree.items
    assert tree.moves == []
    assert view._queue_files_selection_status.call_count == 0


def test_blank_folder_does_not_create_fake_selection():
    tree = Tree(names=())
    view = make_view(tree)
    assert RESTORE(view) is False
    assert tree.currentItem() is None
    assert tree.selectedItems() == []
    assert tree.deliberate_blank_selection is False


def test_wrong_folder_does_not_consume_blank_selection():
    tree = Tree()
    view = make_view(tree)
    launcher, _panel = make_launcher(view)
    view.current_directory = lambda: 'F:/OTHER'
    launcher.navigate_files_exp_folder = Mock(return_value=False)
    assert EXP_RIGHT(launcher) is False
    assert tree.deliberate_blank_selection is True
    assert tree.selectedItems() == []
    assert launcher.remote_focus_area.call_count == 0


def test_exp_context_forward_to_list_uses_same_restore():
    tree = Tree()
    view = make_view(tree)
    launcher, _panel = make_launcher(view)
    queued = []
    dispatch = actual(APP, 'Launcher', '_dispatch_files_column_context_navigation',
                      {'QTimer': NS(singleShot=lambda _ms, fn: queued.append(fn)),
                       'Qt': NS(FocusReason=NS(ShortcutFocusReason=1))})
    launcher._remote_context_wheel = None
    launcher.pointer_warp_enabled = False
    dispatch(launcher, NS(close=Mock()), 'directory')
    assert tree.deliberate_blank_selection
    queued.pop(0)()
    assert tree.currentItem() is tree.items[0]
    assert tree.items[0].isSelected()


def test_keyboard_insert_and_windows_menu_key_contract_stays_untouched():
    assert "tree.deliberate_blank_selection = True" in VIEW
    assert "event.key() == getattr(Qt.Key, 'Key_Menu', None)" in APP
