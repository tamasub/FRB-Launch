"""Search result / behaves as if its target were reached through Files Exp.

Tests are intentionally Qt-free: a lookup cannot mutate the Exp model, and
only a committed folder navigation may update the List/breadcrumb Location.
"""
import ast
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from search_exp_origin import search_exp_origin, search_exp_origin_from_panel


def extract_method(module, name, env=None):
    source = ast.parse((ROOT / 'src' / module).read_text(encoding='utf-8'))
    fn = next(n for cls in source.body if isinstance(cls, ast.ClassDef)
              for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    space = dict(env or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(ROOT / 'src' / module), 'exec'), space)
    return space[name]


def _virtual_link(entry, name='Shared'):
    return {'source': 'launch_json', 'kind': 'linked_directory',
            'title': name, 'page_id': 'work', 'item_id': 'link',
            'node_id': 'item:work:link', 'lineage': ('page:work', 'item:work:link'),
            'breadcrumbs': ('My Work', name),
            'row': {'launch_browse_target': entry}, 'children': []}


def test_registered_exp_root_becomes_search_origin_not_direct_root():
    root = r'F:\FRB\tools'
    result = search_exp_origin(r'F:\FRB\tools\Studio', [
        ('Tools (logical)', {'path': root, 'studio_identity': {'item_id': 'tools'}}),
        ('PC', {'path': 'PC', 'pc': True})], lambda x: x)
    assert result == {'registered_root': {
        'root_path': root, 'title': 'Tools (logical)', 'root_id': 'tools'}}
    assert 'absolute_location' not in result


def test_json_linked_folder_preferred_and_nested_subpath_keeps_ancestry():
    linked = _virtual_link(r'F:\FRB\tools', 'Studio Workspace')
    roots = [('My Work', {'virtual': {'source': 'launch_json', 'kind': 'page',
              'children': [linked]}}),
             ('Physical shortcuts', {'path': r'F:\FRB'})]
    assert search_exp_origin(r'F:\FRB\tools\src', roots, lambda x: x) == {
        'mount_origin': {'node': linked, 'entry_path': r'F:\FRB\tools'}}


def test_longest_root_wins_and_unrelated_context_falls_back_to_absolute_only():
    roots = [('FRB', {'path': r'F:\FRB'}),
             ('Tools', {'path': r'F:\FRB\tools', 'studio_identity': {'item_id': 't'}})]
    assert search_exp_origin(r'F:\FRB\tools\src', roots, lambda x:x)['registered_root']['title'] == 'Tools'
    assert search_exp_origin(r'D:\other', roots, lambda x:x) == {'absolute_location': True}
    assert search_exp_origin('', roots, lambda x:x) == {'absolute_location': True}


def test_model_resolution_is_read_only_and_does_not_add_exp_root():
    class Item:
        def __init__(self, name, info): self.name, self.info = name, info
        def text(self): return self.name
        def data(self, role): return self.info
    class Root:
        def __init__(self): self.children = [Item('Saved', {'path': r'C:\saved'})]
        def rowCount(self): return len(self.children)
        def child(self, i): return self.children[i]
    root = Root()
    panel = NS(model=NS(invisibleRootItem=lambda:root))
    assert search_exp_origin_from_panel(r'C:\saved\items', panel, lambda x:x, 101)['registered_root']['title'] == 'Saved'
    assert len(root.children) == 1


def test_committing_search_ex_folder_uses_snapshotted_origin_after_search_cleared(tmp_path):
    path = tmp_path / 'docs'; path.mkdir()
    calls=[]
    origin={'registered_root':{'root_path':str(tmp_path),'title':'Work','root_id':'w'}}
    source=NS(data=lambda role:{'slash_transient':True,
                 'slash_search_result':True,'slash_search_origin':origin})
    view=NS(isVisible=lambda:True,_workspace_mode='files',
            go_to_directory=lambda target,**kwargs:calls.append(('go',target,kwargs)) or True)
    owner=NS(expanded_view=view,_leave_search_before_exp_navigation=lambda:calls.append('clear'),
             _current_remote_files_exp=lambda: None)
    fn=extract_method('app.py','navigate_files_exp_folder',{
        'Path':Path,'Qt':NS(ItemDataRole=NS(UserRole=100))})
    assert fn(owner,str(path),origin_item=source)
    assert calls == ['clear',('go',str(path),{'preserve_remote_popup':True,
                           'registered_root':origin['registered_root']})]


def test_knowledge_of_mount_changes_breadcrumb_only_on_commit(tmp_path):
    linked=_virtual_link(str(tmp_path),'Team Workspace')
    folder=tmp_path/'child';folder.mkdir()
    opts=search_exp_origin(str(folder), [('My Work', {'virtual':
         {'source':'launch_json','kind':'page','children':[linked]}})],lambda x:x)
    seen=[]
    class View:
        _filesystem_entry_origin = {'node':{'title':'stale'},'entry_path':str(tmp_path/'stale')}
        _registered_root_origin = None
        _direct_entry_root = 'stale'
        _virtual_directory_node = None
        middle = None
        launcher = NS(remote_window=None)
        path = []
        def refresh_middle(self): seen.append('refresh')
    view=View()
    assert not seen and view._direct_entry_root == 'stale', 'lookup cannot navigate'
    fn=extract_method('expanded_view.py','go_to_directory',{
        'normalized_directory':lambda x:str(x),
        'directory_row':lambda x:{'title':Path(x).name,'launch_browse_target':x},
        'Qt':object})
    assert fn(view,str(folder), preserve_remote_popup=True, **opts)
    assert seen==['refresh']
    assert view._filesystem_entry_origin == {'node':linked,'entry_path':str(tmp_path)}
    assert view._direct_entry_root is None and view._registered_root_origin is None


def test_direct_absolute_fallback_never_inherits_previous_root(tmp_path):
    folder=tmp_path/'elsewhere';folder.mkdir()
    seen=[]
    view=NS(_filesystem_entry_origin={'node':{},'entry_path':'old'},
            _direct_entry_root='old',_registered_root_origin={'root_path':'old'},
            _virtual_directory_node={'source':'old'},path=[],
            refresh_middle=lambda:seen.append('refresh'),
            launcher=NS(remote_window=None))
    fn=extract_method('expanded_view.py','go_to_directory',{
        'normalized_directory':lambda x:str(x),
        'directory_row':lambda x:{'title':Path(x).name},'Qt':object})
    assert fn(view,str(folder),preserve_remote_popup=True,absolute_location=True)
    assert view._filesystem_entry_origin is None and view._direct_entry_root is None
    assert view._registered_root_origin is None and view._virtual_directory_node is None
    assert seen == ['refresh']


def test_search_virtual_linked_folder_carries_json_mount_even_as_current_folder(tmp_path):
    """The EX first-row Enter must not silently forget its JSON origin."""
    source = (ROOT/'src/slash_exp_navigation.py').read_text('utf-8')
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == 'slash_source_from_search_result')
    class FakeItem:
        def __init__(self, icon, title): self.info = {}; self.title = title
        def setData(self, value, role): self.info[role] = value
    code = {'QStandardItem':FakeItem, 'QIcon':lambda:None,
            'os':os, '_DATA_ROLE':101,'_LOADED_ROLE':102}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),
                 '<slash-search>','exec'),code)
    row={'page_id':'work','item_id':'link','item_kind':'directory',
         '_main_search_result':True, 'title':'Workspace'}
    view=NS(middle=NS(tree=NS(currentItem=lambda:row)),row_data=lambda item:item)
    node=_virtual_link(str(tmp_path),'Workspace')
    old_modules = sys.modules.get('launch_virtual_tree')
    # The function's local import resolves through the installed real module;
    # its authoritative lookup can be replaced without PySide6 dependencies.
    import launch_virtual_tree
    original=launch_virtual_tree.virtual_lookup_node
    launch_virtual_tree.virtual_lookup_node=lambda *args:node
    try:
        launcher=NS(pages=[],authored_items=[],data={},
                    expander=lambda:NS(expand=lambda x:x))
        item=code['slash_source_from_search_result'](launcher,view,None)
    finally:
        launch_virtual_tree.virtual_lookup_node=original
    info=item.info[101]
    assert info['linked_path']==str(tmp_path)
    assert info['slash_transient'] is True
    assert info['slash_mount_origin']=={'node':node,'entry_path':str(tmp_path)}
    assert item.info[102] is True


def test_registered_origin_renders_the_authored_exp_root_title_as_god():
    """A physical path's UI breadcrumb starts at the registered root label."""
    fn=extract_method('expanded_view.py', '_physical_breadcrumb_segments')
    view=NS(_filesystem_entry_origin=None, _direct_entry_root=None,
            _registered_root_origin={'root_path':r'F:\FRB\tools',
                                     'title':'Tools / Registered', 'root_id':'t'})
    crumb=fn(view,r'F:\FRB\tools\Studio\src')
    assert [label for label, _ in crumb] == ['Tools / Registered','Studio','src']
    assert crumb[0][1] == ('physical',r'F:\FRB\tools')


def test_json_mount_origin_renders_virtual_parents_not_drive_root():
    node=_virtual_link(r'F:\FRB\tools', 'Studio Workspace')
    fn=extract_method('expanded_view.py', '_physical_breadcrumb_segments')
    virtual_crumbs=[('My Work',('virtual','work','')),
                    ('Studio Workspace',('virtual','work','link'))]
    view=NS(_filesystem_entry_origin={'node':node,'entry_path':r'F:\FRB\tools'},
            _direct_entry_root=None,_registered_root_origin=None,
            _virtual_breadcrumb_segments=lambda target: virtual_crumbs)
    expected=virtual_crumbs+[('src',('physical',r'F:\FRB\tools\src'))]
    crumb=fn(view,r'F:\FRB\tools\src')
    assert crumb == expected
    assert all('F:' not in name for name, _ in crumb)


def test_search_ex_descendant_keeps_origin_without_loading_exp_tree(tmp_path):
    folder=tmp_path/'root'; nested=folder/'child'; nested.mkdir(parents=True)
    origin={'registered_root':{'root_path':str(folder),'title':'Saved Root','root_id':'r'}}
    class Item:
        def __init__(self, icon, name): self.name,self.saved,self.children=name,{},[]
        def data(self,role): return self.saved.get(role)
        def setData(self,value,role): self.saved[role]=value
        def setEditable(self,value): pass
        def setToolTip(self,value): pass
        def appendRow(self,row): self.children.append(row)
    root=Item(None,'root')
    root.setData({'path':str(folder),'slash_transient':True,
                  'slash_search_result':True,'slash_search_origin':origin},101)
    nav=NS(launcher=NS(row_icon=lambda row:None))
    fn=extract_method('slash_exp_navigation.py','_transient_physical_folders',{
        'QStandardItem':Item,'os':os,'_DATA_ROLE':101,'_LOADED_ROLE':102})
    fn(nav,root,str(folder))
    assert len(root.children)==1
    child=root.children[0].data(101)
    assert child['slash_search_result'] and child['slash_search_origin'] is origin
    assert child['path']==str(nested)
    assert child.get('slash_mount_origin') is None
