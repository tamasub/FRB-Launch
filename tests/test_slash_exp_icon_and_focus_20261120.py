"""Exp Keyboard Ex: icon alignment + Enter-to-List + executable focus handoff.

Portable CI checks exercise the actual slash Enter handler with the existing
Qt stubs.  Real Windows/Qt pixel alignment and OS focus still need acceptance.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

from test_slash_exp_navigation_20261118 import Item, Panel, make_launcher, nav

from launch_appearance import slash_exp_floating_qss

ROOT = Path(__file__).resolve().parents[1]


def test_scroll_menu_does_not_double_indent_its_icon_column():
    for theme in ('light', 'dark'):
        css = slash_exp_floating_qss(theme, 37)
        # QMenu has native decoration gutter; QTreeWidget already has its own.
        # The previous 15px QTree padding doubled the scroll icon inset.
        assert 'QMenu#slashExpNavigationMenu::item {' in css
        assert 'padding:0px 9px 0px 15px;' in css
        assert 'QTreeWidget#slashExpFixedScrollList::item {' in css
        assert 'padding:0px 9px 0px 6px;' in css
        assert 'QTreeWidget#slashExpFixedScrollList::icon' not in css


def _list_view_for_focus():
    class Tree:
        def __init__(self):
            self.rows = [object(), object()]
            self.current = self.rows[1]
            self.focuses = []
            self.scrolled = None
        def topLevelItemCount(self): return len(self.rows)
        def topLevelItem(self, idx): return self.rows[idx]
        def setCurrentItem(self, row): self.current = row
        def scrollToItem(self, row): self.scrolled = row
        def setFocus(self, reason): self.focuses.append(reason)

    tree = Tree()
    calls = []
    view = SimpleNamespace(isVisible=lambda: True, _workspace_mode='files',
                           middle=SimpleNamespace(tree=tree),
                           row_data=lambda row: {'title': 'row'} if row else None,
                           _focus_files_keyboard_area=lambda area: calls.append(area))
    return view, tree, calls


def test_folder_enter_from_exp_or_list_restores_list_first_row(nav, tmp_path):
    mod, _ = nav
    child = tmp_path / 'folder'
    child.mkdir()
    for original_focus in ('exp', 'list'):
        launcher, recorded = make_launcher()
        view, tree, areas = _list_view_for_focus()
        launcher.expanded_view = view
        launcher.navigate_files_exp_folder = lambda path, **kwargs: recorded.append(('folder',path)) or True
        menu = mod.SlashExpMenu(launcher, Panel([]))
        item = Item('folder', {'path': str(child), 'pc': False})
        assert menu._commit_terminal(item) is True
        assert recorded == [('folder', str(child))]
        assert areas == ['list'], f'Origin {original_focus} should not affect landing'
        assert tree.current is tree.rows[0]
        assert tree.scrolled is tree.rows[0]
        assert len(tree.focuses) == 1


def test_current_folder_virtual_and_pc_enter_also_land_in_list(nav, tmp_path):
    mod, _ = nav
    for kind in ('current', 'virtual', 'pc'):
        launcher, _ = make_launcher()
        view, tree, areas = _list_view_for_focus()
        launcher.expanded_view = view
        folder = tmp_path / 'folder'
        folder.mkdir(exist_ok=True)
        launcher.navigate_files_exp_folder = lambda *_args, **_kw: True
        launcher.navigate_virtual_launch_folder = lambda node: True
        launcher.navigate_files_exp_pc = lambda: True
        menu = mod.SlashExpMenu(launcher, Panel([]))
        if kind == 'current':
            item = Item('Current', {'current_folder': True, 'path': str(folder)})
        elif kind == 'virtual':
            item = Item('Virtual', {'virtual': {'kind': 'folder', 'source': 'launch_json'}})
        else:
            item = Item('PC', {'pc': True})
        assert menu._commit_terminal(item) is True
        assert areas == ['list']
        assert tree.current is tree.rows[0]


def test_file_enter_does_not_force_list_focus(nav, tmp_path):
    mod, _ = nav
    launcher, _ = make_launcher()
    view, tree, areas = _list_view_for_focus()
    launcher.expanded_view = view
    (tmp_path / 'readme.md').write_text('test')
    launcher.run_file_path = lambda *_: True
    menu = mod.SlashExpMenu(launcher, Panel([]))
    assert menu._commit_terminal(Item('README',
        {'path':str(tmp_path / 'readme.md'), 'file':True})) is True
    assert areas == []
    assert tree.current is tree.rows[1]


def test_no_rows_still_focuses_files_list(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    view, tree, areas = _list_view_for_focus()
    tree.rows.clear()
    launcher.expanded_view = view
    assert mod.focus_first_files_list_after_slash_enter(launcher) is True
    assert areas == ['list']
    assert tree.focuses


def test_executable_open_focus_request_uses_guarded_existing_restoration():
    source = ast.parse((ROOT/'src'/'app.py').read_text(encoding='utf-8'))
    main = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    helper = next(n for n in main.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'request_executable_open_focus')
    scheduled = []
    restoration = []
    fake_timer = SimpleNamespace(singleShot=lambda delay, call: scheduled.append((delay, call)))
    fake_window = SimpleNamespace(restore_keyboard_focus=lambda *a, **kw:
                                  restoration.append((a,kw)))
    module = ast.fix_missing_locations(ast.Module(body=[helper],type_ignores=[]))
    env = {'QTimer':fake_timer, 'windows':SimpleNamespace(foreground=lambda:303),
           'window':fake_window}
    exec(compile(module, '<startup-focus>', 'exec'), env)
    env['request_executable_open_focus'](101,'exe_ipc')
    assert [delay for delay,_ in scheduled] == [0,120]
    for _, call in scheduled: call()
    assert all(args[0] == (101,303) for args, _ in restoration)
    assert [kw['restore_current'] for _,kw in restoration] == [True,False]
    main_src = ast.get_source_segment((ROOT/'src'/'app.py').read_text(encoding='utf-8'), main)
    assert "request_executable_open_focus(before, 'exe_ipc')" in main_src
    assert "request_executable_open_focus(initial_foreground, 'exe_preview')" in main_src
