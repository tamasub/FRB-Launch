"""New 2026-11-26 requirements; no real user directories or Qt needed."""
import ast
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import file_index as fi

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT/'src/app.py').read_text(encoding='utf-8')
CLASS = next(n for n in ast.parse(APP).body if isinstance(n, ast.ClassDef) and n.name=='Launcher')

def method(name, **scope):
    n = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[n],type_ignores=[]), 'app.py', 'exec'),scope)
    return scope[name]

def test_default_config_and_public_viewdef(tmp_path):
    for filename in ('config/file_index_options.json','defaults/file_index_options.json'):
        o = fi.load_options(ROOT/filename)
        assert o['auto_update']['startup_delay_seconds']==300
        assert o['exclude_name_contains']==[] and o['index_target']=='files'
    p=tmp_path/'override.json'
    p.write_text(json.dumps({'index_target':'both','max_depth':-1,'auto_update':{'check_interval_minutes':0},'exclude_name_contains':['view_def']}))
    o=fi.load_options(p)
    assert o['max_depth'] is None and o['index_target']=='files'
    assert o['auto_update']['check_interval_minutes']==0 and o['auto_update']['startup_delay_seconds']==300
    assert o['exclude_name_contains']==['view_def']
    v=json.loads((ROOT/'defs/launch/options/file_index_options_view_def_v0_1.json').read_text())
    fields={f['field']:f for s in v['views'][0]['sections'] for f in s['fields']}
    assert {'max_depth','exclude_name_contains','exclude_directories','exclude_directory_globs','scan_error_policy','startup_delay_seconds','check_interval_minutes','max_scan_workers'} <= fields.keys()
    assert 'index_target' not in fields
    assert fields['check_interval_minutes']['edit']['min']==0
    assert v['views'][0]['sections'][1]['dataPath']=='$.auto_update'

def test_zero_timer_and_startup_are_separate():
    timer=Mock(); timer.interval.return_value=1800000;timer.isActive.return_value=False
    o=fi.DEFAULT_OPTIONS | {'update_mode':'auto','auto_update':{'check_interval_minutes':0}}
    self=NS(file_index_check_timer=timer,file_index_settings=o,refresh_file_index=Mock(),auto_refresh_file_index=Mock())
    sync=method('_sync_file_index_periodic_timer',file_index=fi)
    self._sync_file_index_periodic_timer=lambda opts:sync(self,opts)
    sync(self,o);timer.stop.assert_called_once();timer.start.assert_not_called()
    method('refresh_file_index_after_mutation')(self);self.refresh_file_index.assert_not_called()
    method('startup_refresh_file_index')(self);self.auto_refresh_file_index.assert_called_once();timer.start.assert_not_called()
    positive=o | {'auto_update':{'check_interval_minutes':15}}
    self._file_index_startup_pending=True;sync(self,positive);timer.start.assert_not_called()
    self._file_index_startup_pending=False;sync(self,positive);timer.setInterval.assert_called_with(900000);timer.start.assert_called_once()
    assert 'QTimer.singleShot(delay * 1000, self.startup_refresh_file_index)' in APP

def test_main_search_edit_focus_preserves_query_and_history_is_explicit():
    editor=object(); tree=object(); external=object()
    self=NS(search=editor,expanded_view=NS(_main_search_active=True,middle=NS(tree=tree)),_search_list_focus_session=True,clear_global_search_from_list=Mock(return_value=True),_search_list_popup_open=lambda:False)
    context=method('_search_list_focus_context')
    self._search_list_focus_context=lambda w:context(self,w)
    focus={'widget':editor}
    finish=method('_finish_search_list_focus_exit',QApplication=NS(focusWidget=lambda:focus['widget']))
    assert finish(self) is False
    self.clear_global_search_from_list.assert_not_called()
    focus['widget']=external
    assert finish(self) is True
    self.clear_global_search_from_list.assert_called_once_with(preserve_focus=True)
    ef=ast.get_source_segment(APP,next(n for n in CLASS.body if isinstance(n,ast.FunctionDef) and n.name=='eventFilter'))
    assert 'QTimer.singleShot(0, self.show_history_popup)' not in ef
    assert 'self.history_action.triggered.connect(self.toggle_history_popup)' in APP
    assert 'self.show_history_popup()' in ast.get_source_segment(APP,next(n for n in CLASS.body if isinstance(n,ast.FunctionDef) and n.name=='wheel_search_history'))

def test_old_folder_rows_not_used_and_migrate_on_refresh(tmp_path):
    root=tmp_path/'project'; child=root/'data'; child.mkdir(parents=True)
    (child/'one.md').write_text('1'); (child/'two.md').write_text('2');(root/'empty').mkdir()
    db=tmp_path/'old.db';o=fi.load_options(tmp_path/'none')
    fi.refresh_index(db,[str(root)],o)
    with sqlite3.connect(db) as c:
        key=c.execute('SELECT root_key FROM index_roots').fetchone()[0]
        c.execute('INSERT INTO files VALUES (?,?,?,?,?,?)',(str(root/'empty'),'empty','empty',str(root),'',key))
        c.execute('UPDATE index_roots SET options_digest=?',('old',))
    assert not fi.search_index(db,'empty',entry_type='both')
    assert len(fi.search_index(db,'data',entry_type='folders'))==1
    assert fi.search_index(db,'data',1,entry_type='both')[0]['extension']==''
    assert not fi.search_index(db,'one.md',entry_type='folders')
    assert fi.refresh_index(db,[str(root)],o)['count']==2
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM files WHERE extension='' ").fetchone()[0]==0

def test_incremental_view_def_default_and_explicit_exclusion(tmp_path):
    root=tmp_path/'source';root.mkdir();(root/'a_VIEW_DEF.json').write_text('{}')
    db=tmp_path/'db';o=fi.load_options(tmp_path/'none')
    assert fi.refresh_index(db,[str(root)],o)['count']==1
    assert fi.refresh_index(db,[str(root)],o|{'exclude_name_contains':['view_def']})['count']==0
    assert fi.refresh_index(db,[str(root)],o)['count']==1
