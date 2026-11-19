"""Exp Keyboard Ex: breadcrumb-only start, no Exp/List focus branching.

Reuse the actual slash menu with headless Qt stubs already maintained by
20261118 tests. These are Expected/Actual checks, not a Windows GUI claim.
"""
import os
from pathlib import Path
from types import SimpleNamespace

from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Item, Event


def make_view(target, *, virtual=None, current=None, path=None):
    return SimpleNamespace(address_bar=SimpleNamespace(_segments=[('表示名', target)]
                       if target is not None else []),
        _virtual_directory_node=virtual,
        current_directory=lambda: current,
        path=path or [])


def test_home_mywork_slash_opens_virtual_children_instead_of_roots(nav):
    mod, _ = nav
    node = {'source': 'launch_json', 'kind': 'page', 'node_id': 'page:work',
            'page_id': 'work', 'item_id': '', 'title': 'My Work',
            'children': [{'source': 'launch_json', 'kind': 'folder',
                          'node_id': 'item:work:zip', 'page_id': 'work',
                          'item_id': 'zip', 'title': 'ZIP', 'row': {},
                          'children': [{'source': 'launch_json', 'kind': 'file',
                                        'node_id': 'item:work:go', 'title': 'Go!',
                                        'row': {}}]},
                         {'source': 'launch_json', 'kind': 'folder',
                          'node_id': 'item:work:date', 'page_id': 'work',
                          'item_id': 'date', 'title': '日付・定型文', 'row': {},
                          'children': []}]}
    launcher, calls = make_launcher()
    view = make_view(('virtual', 'work', ''), virtual=node)
    panel = Panel([Item('Other root', {'virtual': {'kind': 'page'}})])
    source = mod.slash_source_from_breadcrumb(launcher, view, panel)
    menu = mod.SlashExpMenu(launcher, panel, source_item=source)
    assert [item.text() for item in menu._items()] == ['ZIP', '日付・定型文']
    assert panel.loaded == []  # Exp model must not be reloaded or expanded.
    menu.populate()
    actions = {item.text(): action for action, item in menu._action_items.items()}
    child = menu._submenus[actions['ZIP']]
    assert [item.text() for item in child._items()] == ['（カレントフォルダー）', 'Go!']
    assert calls == []


def test_physical_breadcrumb_drives_slash_independent_of_exp_list_selection(nav, tmp_path):
    mod, key = nav
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'alpha.md').write_text('hi')
    (docs / 'beta.md').write_text('hi')
    inner = docs / 'inner'
    inner.mkdir()
    (inner / 'gamma.md').write_text('hi')
    launcher, calls = make_launcher()
    wrong_exp = Item('Wrong Exp selection', {'path': str(tmp_path)})
    panel = Panel([wrong_exp])
    view = make_view(('physical', str(docs)), current=str(docs))
    source = mod.slash_source_from_breadcrumb(launcher, view, panel)
    menu = mod.SlashExpMenu(launcher, panel, source_item=source)
    assert [i.text() for i in menu._items()] == ['inner', 'alpha.md', 'beta.md']
    assert panel.loaded == []
    menu.populate()
    inner_action = next(a for a,i in menu._action_items.items() if i.text() == 'inner')
    child = menu._submenus[inner_action]
    assert [i.text() for i in child._items()] == ['（カレントフォルダー）', 'gamma.md']
    assert calls == []  # Merely opening / and Right never moves the breadcrumb.
    # Enter on a physical child still uses existing folder navigation.
    menu._commit_terminal(menu._action_items[inner_action])
    assert calls == [('commit_folder', str(inner))]


def test_stale_physical_breadcrumb_does_not_fallback_to_exp_roots(nav, tmp_path):
    mod, _ = nav
    launcher, _ = make_launcher()
    docs = tmp_path / 'docs'; docs.mkdir()
    elsewhere = tmp_path / 'elsewhere'; elsewhere.mkdir()
    panel = Panel([Item('Stale root', {'path': str(elsewhere)})])
    view = make_view(('physical', str(docs)), current=str(elsewhere))
    assert mod.slash_source_from_breadcrumb(launcher, view, panel) is None


def test_breadcrumb_virtual_identity_must_match_actual_current_json_node(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    node = {'source': 'launch_json', 'kind': 'page', 'page_id': 'work',
            'item_id': '', 'title': 'My Work', 'children': []}
    panel = Panel([Item('Other root', {'virtual': node})])
    assert mod.slash_source_from_breadcrumb(launcher,
        make_view(('virtual', 'another', ''), virtual=node), panel) is None


def test_slash_pc_breadcrumb_uses_pc_drives_not_any_selected_list_file(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    pc = Item('PC', {'pc': True})
    panel = Panel([Item('MyWork', {'virtual': {'kind': 'page'}}), pc])
    view = make_view(None, path=[{'_system_drives_root': True}])
    assert mod.slash_source_from_breadcrumb(launcher, view, panel) is pc


def test_missing_directory_returns_error_not_root_or_temporary_registration(nav, tmp_path):
    mod, _ = nav
    launcher, _ = make_launcher()
    panel = Panel([Item('MyWork', {'virtual': {'kind': 'page'}})])
    view = make_view(('physical', str(tmp_path / 'gone')), current=str(tmp_path / 'gone'))
    assert mod.slash_source_from_breadcrumb(launcher, view, panel) is None
    assert len(panel.root.children) == 1


def test_slash_current_location_ignores_list_folder_highlight(nav, tmp_path):
    mod, _ = nav
    launcher, _ = make_launcher()
    docs = tmp_path / 'docs'; docs.mkdir()
    (docs / 'file.md').write_text('hi')
    other = docs / 'other'; other.mkdir()
    panel = Panel([Item('other', {'path': str(other)})])
    view = make_view(('physical', str(docs)), current=str(docs))
    for list_highlight in ('file.md', 'other', None):
        view.list_highlight = list_highlight
        source = mod.slash_source_from_breadcrumb(launcher, view, panel)
        menu = mod.SlashExpMenu(launcher, panel, source_item=source)
        assert [i.text() for i in menu._items()] == ['other', 'file.md']


def test_virtual_empty_node_does_not_revert_to_global_exp_roots(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    node = {'source': 'launch_json', 'kind': 'folder', 'page_id': 'work',
            'item_id': 'empty', 'node_id': 'item:work:empty',
            'title': 'empty', 'children': []}
    source = mod.slash_source_from_breadcrumb(launcher,
        make_view(('virtual', 'work', 'empty'), virtual=node),
        Panel([Item('Global root', {'path': '/tmp'})]))
    menu = mod.SlashExpMenu(launcher, Panel([Item('Global root', {'path': '/tmp'})]),
                            source_item=source)
    assert menu._items() == []


def test_linked_directory_right_then_enter_keeps_logical_mount(nav, tmp_path):
    """Right without committing the linked root must not lose its JSON alias."""
    mod, key = nav
    launcher, calls = make_launcher()
    launcher.expander = lambda: SimpleNamespace(expand=lambda path: path)
    base = tmp_path / 'registered'
    child = base / 'docs'; child.mkdir(parents=True)
    (child / 'note.md').write_text('hi')
    virtual = {'source': 'launch_json', 'kind': 'page',
               'page_id': 'work', 'item_id': '', 'node_id': 'page:work',
               'title': 'My Work', 'children': [
                   {'source': 'launch_json', 'kind': 'linked_directory',
                    'page_id': 'work', 'item_id': 'linked',
                    'node_id': 'item:work:linked', 'title': 'Files',
                    'row': {'launch_browse_target': str(base)}, 'children': []}]}
    view = make_view(('virtual', 'work', ''), virtual=virtual)
    panel = Panel([Item('Global', {'path': '/not-used'})])
    root_source = mod.slash_source_from_breadcrumb(launcher, view, panel)
    menu = mod.SlashExpMenu(launcher, panel, source_item=root_source)
    root_entries = menu._items()
    linked = root_entries[0]
    assert linked.data(mod._DATA_ROLE)['linked_path'] == str(base)
    child_menu = mod.SlashExpMenu(launcher, panel, root=menu,
                                   source_item=linked, parent=menu)
    entries = child_menu._items()
    nested = next(item for item in entries if item.text() == 'docs')
    origin = nested.data(mod._DATA_ROLE)['slash_mount_origin']
    assert origin['entry_path'] == str(base)
    assert origin['node'] is virtual['children'][0]
    deeper = mod.SlashExpMenu(launcher, panel, root=menu,
                              source_item=nested, parent=child_menu)
    assert [x.text() for x in deeper._items()] == [
        '（カレントフォルダー）', 'note.md']
    child_menu._commit_terminal(nested)
    assert calls == [('commit_folder', str(child))]


def test_app_slash_folder_commit_passes_mount_only_for_linked_transient(nav, tmp_path):
    import ast
    from types import SimpleNamespace
    from PySide6.QtCore import Qt
    app = (Path(__file__).resolve().parents[1] / 'src' / 'app.py').read_text('utf-8')
    method = next(n for c in ast.parse(app).body if isinstance(c, ast.ClassDef)
                  for n in c.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'navigate_files_exp_folder')
    namespace = {'Path': Path, 'Qt': Qt}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 '<app linked mount commit>', 'exec'), namespace)
    recorded = []
    view = SimpleNamespace(isVisible=lambda: True, _workspace_mode='files',
        go_to_directory=lambda path, **kw: recorded.append((path, kw)) or True)
    origin = {'node': {'source': 'launch_json', 'kind': 'linked_directory'},
              'entry_path': str(tmp_path)}
    mod, _ = nav
    transient = mod.QStandardItem(mod.QIcon(), 'child')
    transient.setData({'path': str(tmp_path), 'slash_transient': True,
                       'slash_mount_origin': origin}, mod._DATA_ROLE)
    panel = SimpleNamespace(current_registered_root=lambda *a, **kw: (
        1/0))  # This would be an invalid second authority.
    obj = SimpleNamespace(expanded_view=view, _current_remote_files_exp=lambda: panel)
    assert namespace['navigate_files_exp_folder'](obj, str(tmp_path),
                                                 origin_panel=panel, origin_item=transient)
    assert recorded[0][1]['mount_origin'] is origin
    assert recorded[0][1]['registered_root'] is None
