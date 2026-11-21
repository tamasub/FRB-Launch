"""Regression: visible UI preferences and Keyboard Ex Page keys (Qt-free)."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))

from folder_header_preferences import (
    VIRTUAL_BASELINE, virtual_header_layout_key, capture_virtual_header_layout,
    apply_virtual_header_layout, load_virtual_header_layout,
    save_virtual_header_layout)
from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Item, Event


class Settings:
    def __init__(self):
        self.data = {}
        self.sync_count = 0
    def value(self, key, default=None): return self.data.get(key, default)
    def setValue(self, key, value): self.data[key] = value
    def remove(self, key): self.data.pop(key, None)
    def sync(self): self.sync_count += 1


class Header:
    def __init__(self, virtual=True):
        self.widths = [300, 350, 145, 0 if virtual else 150, 55]
        self.order = list(range(5))
    def sectionSize(self, index): return self.widths[index]
    def resizeSection(self, index, width): self.widths[index] = width
    def logicalIndex(self, visual): return self.order[visual]
    def visualIndex(self, logical): return self.order.index(logical)
    def moveSection(self, old, new): self.order.insert(new, self.order.pop(old))


def method(cls, name, source, glb=None):
    mod = ast.parse((SRC / source).read_text('utf8'))
    node = next(n for n in mod.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(glb or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<production method>', 'exec'), scope)
    return scope[name]


def test_virtual_folder_key_stable_for_rename_and_distinct_for_siblings():
    page = dict(page_id='work', node_id='page:work', title='My Work')
    same = dict(page_id='work', node_id='page:work', title='仕事')
    child = dict(page_id='work', node_id='item:work:folderA', title='フォルダー')
    assert virtual_header_layout_key(page) == virtual_header_layout_key(same)
    assert virtual_header_layout_key(page) != virtual_header_layout_key(child)
    assert virtual_header_layout_key({}) is None


def test_logical_width_save_restore_and_default_cleanup():
    settings = Settings()
    node = dict(page_id='work', node_id='page:work')
    key = virtual_header_layout_key(node)
    header = Header()
    assert load_virtual_header_layout(settings, key) == VIRTUAL_BASELINE
    header.resizeSection(0, 485)
    header.moveSection(2, 1)
    edited = capture_virtual_header_layout(header)
    assert save_virtual_header_layout(settings, key, edited)
    reopened = Header()
    assert apply_virtual_header_layout(reopened, load_virtual_header_layout(settings, key))
    assert reopened.widths[:3] == [485, 350, 145]
    assert reopened.order == edited['order']
    assert reopened.widths[3] == 0  # Hidden section not inadvertently made visible
    assert save_virtual_header_layout(settings, key, VIRTUAL_BASELINE)
    assert key not in settings.data


def test_switch_between_logical_folders_restores_their_own_widths():
    restore = method('ExpandedLauncherView', '_restore_middle_header_for_virtual',
                     'expanded_view.py')
    settings = Settings()
    h = Header()
    node_a = dict(page_id='work', node_id='page:work')
    node_b = dict(page_id='work', node_id='item:work:other')
    key_a = virtual_header_layout_key(node_a)
    save_virtual_header_layout(settings, key_a, dict(widths=[475, 350, 145],
                                                     order=list(range(5))))
    view = NS(_middle_header_layout_directory=None,
              _middle_header_layout_key=None,
              _middle_header_restoring=False,
              launcher=NS(settings=settings),
              middle=NS(tree=NS(header=lambda: h)))
    restore(view, node_a)
    assert h.sectionSize(0) == 475
    restore(view, node_b)
    assert h.sectionSize(0) == 300
    restore(view, node_a)
    assert h.sectionSize(0) == 475


def test_user_drag_saves_logical_header_but_layout_resize_does_not():
    save = method('ExpandedLauncherView', '_save_middle_header_state',
                  'expanded_view.py', dict(capture_header_layout=lambda h: None))
    settings = Settings()
    h = Header()
    node = dict(page_id='work', node_id='page:work')
    key = virtual_header_layout_key(node)
    view = NS(_middle_header_restoring=False,
              _middle_header_virtual=True,
              _middle_header_mouse_down=False,
              _middle_header_layout_key=key,
              _middle_header_baseline=dict(widths=[300, 156, 98, 150], order=list(range(5))),
              _middle_header_last_saved_layout=VIRTUAL_BASELINE,
              _preview_maximized=False,
              launcher=NS(settings=settings),
              middle=NS(tree=NS(header=lambda: h)))
    h.resizeSection(0, 480)
    save(view, 'resize', 0)
    assert key not in settings.data
    view._middle_header_mouse_down = True
    save(view, 'resize', 0)
    assert load_virtual_header_layout(settings, key)['widths'][0] == 480
    assert settings.sync_count == 1


def test_height_budget_is_launch_75_percent_or_less():
    from test_slash_exp_navigation_20261118 import nav as fixture_nav  # noqa
    # Pure calculation is checked independent of Windows Qt DPI/layout.
    import importlib.util
    source = (SRC / 'slash_exp_navigation.py').read_text('utf8')
    tree = ast.parse(source)
    const = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'SLASH_LAUNCH_HEIGHT_RATIO'
                         for t in n.targets))
    assert ast.literal_eval(const) == 0.75
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == 'slash_popup_height_budget')
    env = {'SLASH_LAUNCH_HEIGHT_RATIO': 0.75}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<height rule>', 'exec'), env)
    budget = env['slash_popup_height_budget']
    assert budget(700, 800, 900) == 600
    assert budget(370, 800, 900) == 370
    assert budget(700, 800, 400) == 400


def test_popup_page_keys_move_selection_in_scroll_widget(nav):
    mod, key = nav
    key.Key_PageUp = 108
    key.Key_PageDown = 109
    launcher, calls = make_launcher()
    # Real QTreeWidget has height(); give the portable test double the same API.
    roots = [Item('entry-%03d' % i, {'file': True}) for i in range(95)]
    menu = mod.SlashExpMenu(launcher, Panel(roots))
    menu.populate()
    assert menu._scroll_tree is not None
    menu._scroll_tree.height = lambda: menu._scroll_tree.fixed_height
    menu._set_scroll_current_action(next(iter(menu._action_items)))
    before = menu._selected()[0]
    down = Event(key.Key_PageDown)
    menu.keyPressEvent(down)
    assert down.accepted
    assert menu._selected()[0] is not before
    assert menu._scroll_tree.scrolled[-1] is menu._scroll_items[menu._selected()[0]]
    up = Event(key.Key_PageUp)
    menu.keyPressEvent(up)
    assert up.accepted
    assert menu._selected()[0] is before
    assert calls == []


def test_page_up_focuses_real_exp_tree_when_go_up_selects_exp():
    # Read the actual PageUp handoff as a requirement, without globally
    # mocking 12K lines of Launcher dependencies.
    source = (SRC / 'app.py').read_text('utf8')
    assert "getattr(self, '_files_operating_target', None) == 'files_exp'" in source
    assert "handoff('exp')" in source
    assert 'view.go_up(keep_middle_focus=True)' in source


def test_floating_root_and_child_do_not_exceed_75_percent_of_launch(nav):
    mod, key = nav
    launcher, _ = make_launcher()  # height=650, 75%=487
    nested = Item('child.txt', {'file': True})
    roots = [Item('folder', {'virtual': {'kind': 'folder', 'node_id': 'a'}}, nested)]
    roots += [Item('file-%03d' % i, {'file': True}) for i in range(100)]
    assert mod.popup_exp_navigator(launcher, Panel(roots), mod.QPoint(230, 60),
                                   list_height=720, first_column_width=360)
    menu = launcher._slash_exp_navigation_menu
    assert menu.maximum_height == 487
    assert menu._scroll_tree.fixed_height <= 487 - 90
    menu._set_scroll_current_action(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    submenu = menu._submenus[next(iter(menu._action_items))]
    assert submenu.maximum_height <= 487


def test_pageup_at_list_root_changes_real_keyboard_focus_in_app():
    fn = method('Launcher', 'expanded_tree_key', 'app.py', glb={
        'Qt': NS(Key=NS(Key_Right=20, Key_Up=21, Key_Down=22,
                        Key_PageUp=23, Key_PageDown=24, Key_Escape=25,
                        Key_Left=26),
                 KeyboardModifier=NS(NoModifier=0, ControlModifier=2,
                                     ShiftModifier=1, AltModifier=4)),
        'QAbstractItemView': NS(State=NS(EditingState=33))})

    class Tree:
        def __init__(self): self.first = object()
        def viewport(self): return object()
        def topLevelItemCount(self): return 1
        def topLevelItem(self, _index): return self.first
        def currentItem(self): return self.first

    tree = Tree()
    left = NS(tree=Tree()); right = NS(tree=Tree())
    pane = NS(tree=tree)
    handoffs = []
    launcher = NS(_files_operating_target='directory',
                  page_key=lambda _: False)
    view = NS(left=left, middle=pane, right=right,
              isVisible=lambda: True,
              row_data=lambda _: {'title': 'first'},
              _focus_files_keyboard_area=lambda area: handoffs.append(area))
    launcher.expanded_view = view

    def press_root_pageup():
        event = NS(key=lambda: 23, modifiers=lambda: 0, accept=lambda: None)
        return fn(launcher, tree, event)

    def visit_root(**_kw): launcher._files_operating_target = 'files_exp'
    view.go_up = visit_root
    assert press_root_pageup() is True
    assert handoffs == ['exp']

    # Ordinary PageUp to a real parent keeps List focus.
    handoffs.clear()
    launcher._files_operating_target = 'directory'
    view.go_up = lambda **_kw: None
    assert press_root_pageup() is True
    assert handoffs == []
