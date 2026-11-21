"""Qt-free tests of the visible-only watch policy and production callbacks.

A Windows/PySide6 acceptance test remains necessary for native filesystem
notifications, folder renames and on-screen repainting.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS
import sys

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from visible_directory_watch import (normalized_watch_path, physical_crumb_paths,
                                     breadcrumb_parent_watches, exp_visible_watches,
                                     stat_directory_identity, relocated_crumb_directory)


def extract_method(file, cls, name, extra=None):
    root = ast.parse((SRC / file).read_text('utf-8'))
    klass = next(x for x in root.body if isinstance(x, ast.ClassDef) and x.name == cls)
    method = next(x for x in klass.body if isinstance(x, ast.FunctionDef) and x.name == name)
    ns = {'os': os, 'normalized_watch_path': normalized_watch_path,
          'breadcrumb_parent_watches': breadcrumb_parent_watches,
          'physical_crumb_paths': physical_crumb_paths,
          'stat_directory_identity': stat_directory_identity,
          'relocated_crumb_directory': relocated_crumb_directory,
          'exp_visible_watches': exp_visible_watches,
          'QAbstractItemView': NS(State=NS(EditingState=1, DraggingState=2))}
    ns.update(extra or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(SRC / file), 'exec'), ns)
    return ns[name]


class FakeWatcher:
    def __init__(self): self.paths = []
    def directories(self): return list(self.paths)
    def addPath(self, p):
        self.paths.append(p)
        return True
    def removePath(self, p):
        self.paths.remove(p)
        return True


class FakeTimer:
    def __init__(self): self.count = 0
    def start(self): self.count += 1


def test_crumb_watch_only_physical_parent_deduplicated(tmp_path):
    a = tmp_path/'root'; b = a/'child'; c = b/'sub'
    c.mkdir(parents=True)
    segments = [('JSON page', ('virtual','system','foo')),
                ('Root', ('physical', str(a))),
                ('Child', ('physical', str(b))),
                ('Sub', ('physical', str(c))),
                ('Repeat child', ('physical', str(b)))]
    assert breadcrumb_parent_watches(segments) == [
        normalized_watch_path(tmp_path), normalized_watch_path(a),
        normalized_watch_path(b)]
    assert len(breadcrumb_parent_watches(segments, limit=2)) == 2


def test_exp_watch_only_visible_row_parents_and_open_children(tmp_path):
    root = tmp_path/'root'; a=root/'a'; b=root/'b'; c=a/'sub'
    c.mkdir(parents=True); b.mkdir()
    # The closed directory a is visible but its contents are not.
    rows = [(str(a), False, None), (str(b), True, None)]
    assert exp_visible_watches(rows) == [normalized_watch_path(root),
                                         normalized_watch_path(b)]
    # A scrolled-away row never arrives at this selector.
    assert normalized_watch_path(a) not in exp_visible_watches(rows)
    assert exp_visible_watches([(None, True, str(c))]) == [normalized_watch_path(c)]
    assert len(exp_visible_watches(rows, limit=1)) == 1


def test_breadcrumb_watcher_tracks_location_skips_virtual_and_ignores_stale(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; a.mkdir(); b.mkdir()
    watcher=FakeWatcher(); timer=FakeTimer(); bar=NS(_segments=[('A',('physical',str(a)))])
    view=NS(address_bar=bar, _workspace_mode='files', _virtual_directory_node=None,
            _breadcrumb_directory_watcher=watcher, _breadcrumb_watched_directories=set(),
            _breadcrumb_pending_directories=set(), _breadcrumb_refresh_timer=timer,
            _breadcrumb_directory_identities={})
    sync=extract_method('expanded_view.py','ExpandedLauncherView','_sync_breadcrumb_directory_watch')
    queue=extract_method('expanded_view.py','ExpandedLauncherView','_queue_breadcrumb_auto_refresh')
    sync(view)
    assert watcher.paths == [normalized_watch_path(tmp_path)]
    queue(view,str(tmp_path)); queue(view,str(tmp_path))
    assert timer.count == 2 and len(view._breadcrumb_pending_directories) == 1
    bar._segments=[('JSON',('virtual','page','id'))]
    sync(view)
    assert watcher.paths == [] and not view._breadcrumb_pending_directories
    queue(view,str(tmp_path))
    assert timer.count == 2
    bar._segments=[('B',('physical',str(b)))]
    sync(view)
    assert watcher.paths == [normalized_watch_path(tmp_path)]


def test_breadcrumb_auto_refresh_preserves_history_and_defers_editing(tmp_path):
    a=tmp_path/'a'; a.mkdir(); watcher=FakeWatcher(); timer=FakeTimer()
    bar=NS(_segments=[('A',('physical',str(a)))],
           set_logical_directory=lambda *args, **kwargs: updated.append(('logical', args, kwargs)),
           set_directory=lambda *args, **kwargs: updated.append(('physical', args, kwargs)))
    updated=[]
    tree=NS(state=lambda:1)
    view=NS(address_bar=bar, _workspace_mode='files', _virtual_directory_node=None,
            _breadcrumb_directory_watcher=watcher, _breadcrumb_watched_directories=set(),
            _breadcrumb_pending_directories=set(), _breadcrumb_refresh_timer=timer,
            _breadcrumb_directory_identities={}, _refreshing=False, _inline_rename_active=False,
            launcher=NS(_filesystem_dialog_depth=0), middle=NS(tree=tree),
            current_directory=lambda:str(a), isVisible=lambda:True,
            _physical_breadcrumb_segments=lambda p:[('A', ('physical',p))])
    view._sync_breadcrumb_directory_watch=lambda:extract_method(
        'expanded_view.py','ExpandedLauncherView','_sync_breadcrumb_directory_watch')(view)
    view._sync_breadcrumb_directory_watch()
    queue=extract_method('expanded_view.py','ExpandedLauncherView','_queue_breadcrumb_auto_refresh')
    flush=extract_method('expanded_view.py','ExpandedLauncherView','_flush_breadcrumb_auto_refresh')
    queue(view,str(tmp_path)); flush(view)
    assert not updated and timer.count >= 2
    tree.state=lambda:0
    flush(view)
    assert len(updated)==1 and updated[0][0]=='logical'
    assert not view._breadcrumb_pending_directories


def test_exp_refresh_only_watched_paths_and_defers_rename(tmp_path):
    root=tmp_path/'r'; a=root/'a'; b=root/'b'; a.mkdir(parents=True); b.mkdir()
    watcher=FakeWatcher(); watchtimer=FakeTimer(); freshtimer=FakeTimer()
    calls=[]
    panel=NS(_visible_dir_watcher=watcher, _visible_dir_paths=set(),
             _visible_exp_pending=set(), _visible_refresh_timer=freshtimer,
             _rename_in_progress=None, _syncing_directory=False,
             _restoring_tree=False, _launcher=NS(_filesystem_dialog_depth=0),
             tree=NS(state=lambda:0), isVisible=lambda:True,
             _visible_exp_rows=lambda:[(str(a), True, None), (str(b),False,None)],
             refresh_directory_branch=lambda path:calls.append(path))
    panel._sync_visible_exp_watches=lambda:extract_method(
        'remote_files_explorer.py','RemoteFilesExplorer','_sync_visible_exp_watches')(panel)
    panel._sync_visible_exp_watches()
    assert set(watcher.paths)=={normalized_watch_path(root), normalized_watch_path(a)}
    queue=extract_method('remote_files_explorer.py','RemoteFilesExplorer',
                         '_queue_visible_exp_auto_refresh')
    flush=extract_method('remote_files_explorer.py','RemoteFilesExplorer',
                         '_flush_visible_exp_auto_refresh')
    queue(panel,str(b))  # Closed, not watched.
    assert not panel._visible_exp_pending
    queue(panel,str(a)); queue(panel,str(root))
    panel._rename_in_progress='renaming'
    flush(panel)
    assert not calls and freshtimer.count>=3
    panel._rename_in_progress=None
    flush(panel)
    assert set(calls)==set(watcher.paths)
    assert not panel._visible_exp_pending


def test_exp_visible_row_collection_does_not_walk_entire_model():
    src=(SRC/'remote_files_explorer.py').read_text('utf-8')
    assert 'indexBelow(index)' in src
    assert 'visited < 256' in src
    assert 'self._visible_dir_watcher.directoryChanged.connect(' in src
    assert 'self._schedule_visible_exp_watch_sync' in src
    assert 'self.refresh_directory_branch(path)' in src


def test_crumb_plain_address_path_and_verified_rename(tmp_path):
    old = tmp_path/'project'; child=old/'work'
    child.mkdir(parents=True)
    segments = [('Project',str(old)), ('Work',str(child))]
    expected = {normalized_watch_path(tmp_path), normalized_watch_path(old)}
    assert set(breadcrumb_parent_watches(segments))==expected
    old_id = stat_directory_identity(str(old))
    child_id = stat_directory_identity(str(child))
    assert old_id and child_id
    ids={normalized_watch_path(old):old_id, normalized_watch_path(child):child_id}
    new=tmp_path/'renamed'; old.rename(new)
    move=relocated_crumb_directory(str(child), segments, ids)
    assert move==(normalized_watch_path(old), normalized_watch_path(new/'work'))


def test_unknown_identity_never_follows_rename(tmp_path):
    old=tmp_path/'from';old.mkdir()
    segments=[('From',('physical',str(old)))]
    old.rename(tmp_path/'to')
    assert relocated_crumb_directory(str(old),segments,{}) is None


def test_crumb_rename_handler_uses_existing_navigation_only_after_identity(tmp_path):
    from_path = tmp_path/'before'; from_path.mkdir()
    to_path = tmp_path/'after';
    identities={normalized_watch_path(from_path):stat_directory_identity(from_path)}
    segments=[('Before', ('physical',str(from_path)))]
    from_path.rename(to_path)
    watcher=FakeWatcher(); timer=FakeTimer(); events=[]
    bar=NS(_segments=segments,
           set_logical_directory=lambda *a,**kw:events.append(('bar',a,kw)),
           set_directory=lambda *a,**kw:events.append(('dir',a,kw)))
    view=NS(address_bar=bar, _workspace_mode='files', _virtual_directory_node=None,
            _breadcrumb_directory_watcher=watcher,
            _breadcrumb_directory_identities=identities,
            _breadcrumb_watched_directories={normalized_watch_path(tmp_path)},
            _breadcrumb_pending_directories={normalized_watch_path(tmp_path)},
            _breadcrumb_refresh_timer=timer, _refreshing=False, _inline_rename_active=False,
            launcher=NS(_filesystem_dialog_depth=0),
            middle=NS(tree=NS(state=lambda:0)), current_directory=lambda:str(from_path),
            isVisible=lambda:True, _direct_entry_root=None,
            _registered_root_origin=None,_filesystem_entry_origin=None,
            _follow_visible_crumb_rename=lambda p:events.append(('follow',p)))
    flush=extract_method('expanded_view.py','ExpandedLauncherView','_flush_breadcrumb_auto_refresh')
    flush(view)
    assert events==[('follow',normalized_watch_path(to_path))]


def test_exp_iterates_only_viewport_visible_rows_with_deep_indent():
    method=extract_method('remote_files_explorer.py','RemoteFilesExplorer',
                          '_visible_exp_rows', {'QModelIndex':lambda:Idx(-1),
                                                'QPoint':lambda x,y:(x,y),
                                                '_DATA_ROLE': 101})
    class Rect:
        def __init__(self, top): self._top=top
        def top(self): return self._top
        def bottom(self): return self._top+16
    # Simulate a tree whose first column occupies only a small part of the
    # viewport and whose first visible row has a deeply indented name.
    class FakeTree:
        def __init__(self): self.scanned=0
        def viewport(self): return NS(height=lambda:55,width=lambda:600)
        def columnWidth(self,_): return 190
        def indexAt(self,p):
            x,y=p
            return Idx(0) if x==188 and y<=10 else Idx(-1)
        def visualRect(self,i): return Rect(i.index*20)
        def isExpanded(self,i): return i.index==0
        def indexBelow(self,i):
            self.scanned+=1
            return Idx(i.index+1) if i.index<7 else Idx(-1)
    class Item:
        def __init__(self,i):self.i=i
        def data(self,role):return {'path':str(self.i),'linked_path':None}
    class Model:
        def itemFromIndex(self,i):return Item(i.index)
    tree=FakeTree()
    panel=NS(tree=tree,model=Model())
    rows=method(panel)
    assert rows==[('0',True,None),('1',False,None),('2',False,None)]
    assert tree.scanned==3


class Idx:
    def __init__(self,index):self.index=index
    def isValid(self):return self.index>=0
    def __eq__(self,other):return isinstance(other,Idx) and self.index==other.index
