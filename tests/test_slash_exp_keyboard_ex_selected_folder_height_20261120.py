"""Exp Keyboard Ex: breadcrumb + filled-green List folder and List-height cap.

Portable tests of production behavior via established Qt stubs. Real Windows
QMenu display/scroll remains a separate acceptance item.
"""
from pathlib import Path
from types import SimpleNamespace

from test_slash_exp_keyboard_ex_breadcrumb_20261120 import make_view
from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Item, Event


class ListRow:
    def __init__(self, selected=True):
        self.selected = selected
    def isSelected(self):
        return self.selected


def list_view(view, row, *, selected=True, green=True, blank=False, multiple=False):
    line = ListRow(selected=selected)
    view.row_data = lambda item: row if item is line else None
    other = ListRow()
    selection = ([line, other] if multiple else [line] if selected else [])
    tree = SimpleNamespace(deliberate_blank_selection=blank,
        property=lambda name: False if green else True,
        selectedItems=lambda: selection,
        currentItem=lambda: line)
    view.middle = SimpleNamespace(tree=tree)
    return view


def test_list_green_physical_folder_extends_breadcrumb_one_level(nav, tmp_path):
    mod, _ = nav
    docs = tmp_path / 'docs'; docs.mkdir()
    sub = docs / 'sub'; sub.mkdir()
    (sub / 'inside.md').write_text('file')
    launcher, _ = make_launcher()
    launcher.expander = lambda: SimpleNamespace(expand=lambda x: x)
    view = make_view(('physical', str(docs)), current=str(docs))
    list_view(view, {'title':'sub', 'item_kind':'directory',
                     'launch_browse_target':str(sub)})
    base = mod.slash_source_from_breadcrumb(launcher, view, Panel([]))
    target = mod.slash_source_with_filled_list_folder(launcher, view, base)
    assert target is not base
    assert target.data(mod._DATA_ROLE)['path'] == str(sub)
    menu = mod.SlashExpMenu(launcher, Panel([]), source_item=target)
    assert [i.text() for i in menu._items()] == ['inside.md']


def test_list_outline_or_file_or_inactive_uses_only_breadcrumb(nav, tmp_path):
    mod, _ = nav
    docs = tmp_path / 'docs'; docs.mkdir()
    sub = docs / 'sub'; sub.mkdir()
    file = docs / 'note.md'; file.write_text('file')
    launcher, _ = make_launcher()
    launcher.expander = lambda: SimpleNamespace(expand=lambda x: x)
    view = make_view(('physical', str(docs)), current=str(docs))
    base = mod.slash_source_from_breadcrumb(launcher, view, Panel([]))
    folder = {'title':'sub', 'item_kind':'directory', 'launch_browse_target':str(sub)}
    file_row = {'title':'note.md','item_kind':'command','_browse_file':str(file)}
    for row, selected, green, blank, multiple in (
        (folder,False,True,True,False),  # remembered outline only
        (folder,True,False,False,False), # inactive selection paints transparent
        (folder,True,True,False,True),  # ambiguous multi-select
        (file_row,True,True,False,False),
    ):
        list_view(view,row,selected=selected,green=green,blank=blank,multiple=multiple)
        assert mod.slash_source_with_filled_list_folder(launcher,view,base) is base


def test_unrelated_selected_folder_does_not_override_breadcrumb(nav, tmp_path):
    mod, _ = nav
    docs = tmp_path / 'docs'; docs.mkdir()
    elsewhere = tmp_path / 'elsewhere'; elsewhere.mkdir()
    launcher, _ = make_launcher()
    launcher.expander=lambda: SimpleNamespace(expand=lambda x:x)
    view=make_view(('physical',str(docs)),current=str(docs))
    list_view(view,{'item_kind':'directory','title':'elsewhere',
                    'launch_browse_target':str(elsewhere)})
    base=mod.slash_source_from_breadcrumb(launcher,view,Panel([]))
    assert mod.slash_source_with_filled_list_folder(launcher,view,base) is base


def test_green_virtual_folder_extends_logical_breadcrumb(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    child = {'kind':'folder','source':'launch_json','page_id':'work',
             'item_id':'docs','node_id':'item:work:docs','title':'Docs',
             'children':[{'kind':'file','node_id':'item:work:run',
                          'title':'Run','row':{}}], 'row':{}}
    page = {'kind':'page','source':'launch_json','page_id':'work',
            'item_id':'','node_id':'page:work','title':'My Work',
            'children':[child]}
    view=make_view(('virtual','work',''),virtual=page)
    list_view(view, {'item_kind':'category','title':'Docs','_launch_virtual_node':child})
    base=mod.slash_source_from_breadcrumb(launcher,view,Panel([]))
    target=mod.slash_source_with_filled_list_folder(launcher,view,base)
    assert target.data(mod._DATA_ROLE)['virtual'] is child
    menu=mod.SlashExpMenu(launcher,Panel([]),source_item=target)
    assert [i.text() for i in menu._items()] == ['Run']


def test_long_list_popup_height_and_cascade_inherit_visible_list_bounds(nav):
    mod, key=nav
    launcher, _=make_launcher()
    nested=Item('file.txt',{'file':True})
    roots=[Item('dir',{'virtual':{'kind':'folder','node_id':'dir'}}, nested)]
    roots += [Item(f'file{i:03d}.md', {'file':True}) for i in range(130)]
    top,bottom = 120,530
    assert mod.popup_exp_navigator(launcher,Panel(roots),mod.QPoint(320,top),
                                   first_column_width=340,list_bottom_y=bottom)
    popup=launcher._slash_exp_navigation_menu
    assert popup._popup_height == bottom-top == 410
    assert popup.maximum_height == 410
    assert popup._scroll_tree is not None
    assert popup._scroll_tree.fixed_height <= 410-90
    action=next(iter(popup._action_items))
    popup._set_scroll_current_action(action)
    popup.keyPressEvent(Event(key.Key_Right))
    submenu=popup._submenus[action]
    assert submenu._popup_height == 410
    assert submenu.maximum_height == 410
    if submenu._fixed_popup_pos is not None:
        assert 120 <= submenu._fixed_popup_pos.y() <= bottom-submenu.height()


def test_initial_list_popup_is_not_stretched_to_full_list_height(nav):
    mod, _ = nav
    launcher, _=make_launcher()
    assert mod.popup_exp_navigator(launcher,Panel([Item('short',{'file':True})]),
                                  mod.QPoint(320,120),first_column_width=310,
                                  list_bottom_y=700)
    popup=launcher._slash_exp_navigation_menu
    assert popup.maximum_height == 580
    assert popup._scroll_tree is None  # short menus keep natural height


def test_green_linked_folder_keeps_json_mount_and_real_files(nav, tmp_path):
    mod, _ = nav
    launcher, _ = make_launcher()
    launcher.expander=lambda: SimpleNamespace(expand=lambda x:x)
    mount=tmp_path/'physical'; mount.mkdir()
    (mount/'hello.md').write_text('ok',encoding='utf-8')
    folder={'kind':'linked_directory','source':'launch_json',
            'page_id':'work','item_id':'link','node_id':'item:work:link',
            'title':'Linked','row':{'launch_browse_target':str(mount)},
            'children':[]}
    page={'kind':'page','source':'launch_json','page_id':'work',
          'item_id':'','node_id':'page:work','title':'My Work',
          'children':[folder]}
    view=make_view(('virtual','work',''),virtual=page)
    list_view(view,{'title':'Linked','item_kind':'directory',
                    '_launch_virtual_node':folder})
    base=mod.slash_source_from_breadcrumb(launcher,view,Panel([]))
    source=mod.slash_source_with_filled_list_folder(launcher,view,base)
    assert source.data(mod._DATA_ROLE)['linked_path'] == str(mount)
    menu=mod.SlashExpMenu(launcher,Panel([]),source_item=source)
    assert [i.text() for i in menu._items()] == ['hello.md']
    assert source.data(mod._DATA_ROLE)['virtual'] is folder
