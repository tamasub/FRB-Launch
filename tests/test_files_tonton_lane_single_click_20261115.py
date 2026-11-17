"""Regression: single click in Files' tonton lane targets the current folder.

Headless AST tests execute the actual production handlers with tiny Qt stubs.
The Windows GUI still needs visual confirmation of the green-outline style.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

VIEW = (Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py').read_text(encoding='utf-8')


def _handlers():
    owner = next(n for n in ast.parse(VIEW).body if isinstance(n, ast.ClassDef)
                 and n.name == 'ExpandedLauncherView')
    selected = ('handle_middle_back_double_click',
                'clear_middle_row_for_folder_operation')
    cls = ast.ClassDef(name='Handler', bases=[], keywords=[],
                       body=[n for n in owner.body if isinstance(n, ast.FunctionDef)
                             and n.name in selected], decorator_list=[])
    qt = NS(MouseButton=NS(LeftButton='left'),
            KeyboardModifier=NS(NoModifier='none'),
            FocusReason=NS(MouseFocusReason='mouse'))
    events = NS(MouseButtonPress='press', MouseButtonRelease='release',
                MouseButtonDblClick='double')
    scope = {'Qt': qt, 'QEvent': NS(Type=events)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 '<expanded_view>', 'exec'), scope)
    return scope['Handler']


class Item:
    def __init__(self, selected=True):
        self.selected = selected

    def isSelected(self):
        return self.selected


class Tree:
    def __init__(self):
        self.row = Item()
        self.deliberate_blank_selection = False
        self.events = []
        self.blank_clicked = lambda: self.events.append('directory-target')

    def currentItem(self):
        return self.row

    def selectedItems(self):
        return [self.row] if self.row.selected else []

    def clearSelection(self):
        assert self.deliberate_blank_selection, 'selection repair must be suppressed first'
        self.row.selected = False
        self.events.append('clear')

    def setFocus(self, reason):
        self.events.append(('focus', reason))

    def viewport(self):
        return self

    def update(self):
        self.events.append('repaint')


class Event:
    def __init__(self, kind='press', button='left', modifiers='none'):
        self.kind, self._button, self._mods = kind, button, modifiers
        self.accepted = False

    def type(self):
        return self.kind

    def button(self):
        return self._button

    def modifiers(self):
        return self._mods

    def accept(self):
        self.accepted = True

    def position(self):
        return NS(toPoint=lambda: NS())


class Demo(_handlers()):
    def __init__(self):
        self.tree = Tree()
        self.middle = NS(tree=self.tree)
        self.middle_back_lane = object()
        self.saved_directory = 'F:/FRB/folder'
        self.go_up_count = 0
        self.status_count = 0
        self.is_visible = True

    def isVisible(self):
        return self.is_visible

    def current_directory(self):
        return self.saved_directory

    def go_up(self):
        self.go_up_count += 1

    def _sync_remote_area_after_mouse_press(self, area):
        self.tree.events.append(('sync', area))

    def _queue_files_selection_status(self):
        self.status_count += 1


def test_lane_single_click_clears_selection_keeps_passive_current_and_folder():
    obj = Demo()
    old_current = obj.tree.currentItem()
    click = Event()
    assert obj.handle_middle_back_double_click(obj.middle_back_lane, click)
    assert click.accepted
    assert obj.tree.selectedItems() == []
    assert obj.tree.currentItem() is old_current  # passive green border survives
    assert obj.tree.deliberate_blank_selection
    assert obj.tree.events == ['clear', ('focus', 'mouse'), 'directory-target', 'repaint']
    assert obj.saved_directory == 'F:/FRB/folder'
    assert obj.go_up_count == 0
    assert obj.status_count == 1


def test_lane_click_fallback_routes_to_directory_target_without_blank_callback():
    obj = Demo()
    obj.tree.blank_clicked = None
    assert obj.handle_middle_back_double_click(obj.middle_back_lane, Event())
    assert ('sync', 'directory') in obj.tree.events
    assert not obj.tree.row.isSelected()


def test_lane_double_click_still_goes_up_but_release_never_clears_again():
    obj = Demo()
    assert obj.handle_middle_back_double_click(obj.middle_back_lane, Event('press'))
    before = list(obj.tree.events)
    assert obj.handle_middle_back_double_click(obj.middle_back_lane, Event('release'))
    assert obj.tree.events == before
    assert obj.handle_middle_back_double_click(obj.middle_back_lane, Event('double'))
    assert obj.go_up_count == 1
    assert obj.tree.events == before


def test_right_click_and_modifier_click_are_not_intercepted():
    obj = Demo()
    assert not obj.handle_middle_back_double_click(obj.middle_back_lane,
                                                    Event(button='right'))
    assert not obj.handle_middle_back_double_click(obj.middle_back_lane,
                                                    Event(modifiers='ctrl'))
    assert obj.tree.row.isSelected()
    assert obj.go_up_count == 0


def test_lane_uses_same_blank_click_semantics_as_tree_and_never_changes_path():
    assert 'tree.deliberate_blank_selection = True' in VIEW
    assert 'tree.clearSelection()' in VIEW
    assert 'tree.viewport().update()' in VIEW
    assert "if event.type() == QEvent.Type.MouseButtonPress:" in VIEW
    assert "self.show_lane_new_menu(event.globalPos())" in VIEW
