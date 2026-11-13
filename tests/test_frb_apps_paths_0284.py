"""0284 migration: opt-in, narrow, idempotent and lossless."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'migrate_frb_apps_paths_0284.py'
spec = importlib.util.spec_from_file_location('frb_0284_paths', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(home):
    return {
        'title':'手動編集は保護する', 'launch_format_version':'0.2-draft',
        'pages':[{'page_id':'work','enabled':True}],
        'items':[
            {'item_id':'one','page_id':'work','item_kind':'command','parent_item_id':'',
             'title':'バッチ', 'description':m.LEGACY_LAUNCH+r'\_build_windows.bat',
             'launch_browse_target':'',
             'launch_actions':[{'launch_action_type':'Open',
                                'launch_target':m.LEGACY_LAUNCH+r'\_build_windows.bat'}]},
            {'item_id':'two','page_id':'work','item_kind':'directory','parent_item_id':'',
             'title':'Studio資材', 'description':'ユーザーの自由な記述。ここは触らない。',
             'launch_browse_target':m.LEGACY_STUDIO+r'\data\json',
             'launch_actions':[{'launch_action_type':'Open',
                                'launch_target':m.LEGACY_STUDIO+r'\data'}]},
            {'item_id':'three','page_id':'work','item_kind':'command','parent_item_id':'',
             'title':'FRB資料', 'description':'研究資料',
             'launch_actions':[{'launch_action_type':'Open','launch_target':r'F:\FRB\data\measure.json'}]},
            {'item_id':'four','page_id':'work','item_kind':'command','parent_item_id':'',
             'title':'似た名前', 'description':'keep',
             'launch_actions':[{'launch_action_type':'Open','launch_target':m.LEGACY_LAUNCH+'Backup\\keep.bat'}]},
        ],
        'launch_variables':[{'variable_id':'studio_root','launch_variable_type':'literal','launch_value':m.LEGACY_STUDIO}],
        'launch_choices':[],
        'extra_my_config':{'日本語':'個人設定', 'archive_path':m.LEGACY_LAUNCH+r'\historical.log'}
    }


def write_fixture(home):
    (home/'config').mkdir(parents=True)
    data=fixture(home)
    (home/m.LIVE_CONFIG).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    index={'enabled':True,'index_mode':'registered',
           'index_folders':[m.LEGACY_LAUNCH,r'F:\FRB\data']}
    (home/m.INDEX_CONFIG).write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return data, index


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)/'FRB_Apps'/'FRB_Launch'
        self.original,self.index=write_fixture(self.home)
        (self.home.parent/'FRB_Studio').mkdir()

    def test_dry_run_does_not_write_or_backup(self):
        a=(self.home/m.LIVE_CONFIG).read_bytes()
        b=(self.home/m.INDEX_CONFIG).read_bytes()
        self.assertEqual(m.migrate(self.home,apply=False),0)
        self.assertEqual((self.home/m.LIVE_CONFIG).read_bytes(),a)
        self.assertEqual((self.home/m.INDEX_CONFIG).read_bytes(),b)
        self.assertFalse((self.home/'backups').exists())

    @mock.patch.object(m, 'app_is_running', return_value=False)
    def test_apply_backs_up_and_keeps_user_data(self, _):
        self.assertEqual(m.migrate(self.home,apply=True),0)
        now=json.loads((self.home/m.LIVE_CONFIG).read_text(encoding='utf-8'))
        self.assertEqual(now['items'][0]['launch_actions'][0]['launch_target'],r'%launch_home%\_build_windows.bat')
        self.assertEqual(now['items'][1]['launch_browse_target'],r'%studio_root%\data\json')
        self.assertEqual(now['items'][0]['description'],str(self.home)+r'\_build_windows.bat')
        self.assertEqual(now['launch_variables'][0]['launch_value'],str(self.home.parent/'FRB_Studio'))
        self.assertEqual(now['extra_my_config'],self.original['extra_my_config'])
        self.assertEqual(now['items'][2],self.original['items'][2])
        self.assertEqual(now['items'][3],self.original['items'][3])
        self.assertEqual(now['items'][1]['title'],'Studio資材')
        index=json.loads((self.home/m.INDEX_CONFIG).read_text(encoding='utf-8'))
        self.assertEqual(index['index_folders'],[str(self.home),r'F:\FRB\data'])
        backup=next((self.home/'backups').glob('frb_apps_paths_0284_*'))
        self.assertEqual(json.loads((backup/'frb_launch_data.json').read_text(encoding='utf-8')),self.original)
        self.assertEqual(json.loads((backup/'file_index_options.json').read_text(encoding='utf-8')),self.index)
        self.assertIn('%launch_home%',(backup/'migration_diff.patch').read_text(encoding='utf-8'))

    @mock.patch.object(m, 'app_is_running', return_value=False)
    def test_idempotence(self, _):
        m.migrate(self.home,apply=True)
        after=(self.home/m.LIVE_CONFIG).read_bytes()
        m.migrate(self.home,apply=True)
        self.assertEqual((self.home/m.LIVE_CONFIG).read_bytes(),after)
        self.assertEqual(len(list((self.home/'backups').glob('frb_apps_paths_0284_*'))),1)

    @mock.patch.object(m, 'app_is_running', return_value=True)
    def test_running_app_blocks_changes(self, _):
        before=(self.home/m.LIVE_CONFIG).read_bytes()
        with self.assertRaisesRegex(RuntimeError,'起動中'):
            m.migrate(self.home,apply=True)
        self.assertEqual((self.home/m.LIVE_CONFIG).read_bytes(),before)
        self.assertFalse((self.home/'backups').exists())

    @mock.patch.object(m, 'app_is_running', return_value=False)
    def test_wrong_layout_blocks_apply(self, _):
        (self.home.parent/'FRB_Studio').rmdir()
        old=(self.home/m.LIVE_CONFIG).read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'FRB_Studio'):
            m.migrate(self.home,apply=True)
        self.assertEqual((self.home/m.LIVE_CONFIG).read_bytes(),old)
        self.assertFalse((self.home/'backups').exists())

    def test_unknown_field_and_histories_untouched(self):
        after, changes=m.migrate_data(self.original,launch_home=str(self.home),studio_home=str(self.home.parent/'FRB_Studio'))
        self.assertEqual(after['extra_my_config'],self.original['extra_my_config'])
        self.assertEqual(self.original['items'][0]['launch_actions'][0]['launch_target'],m.LEGACY_LAUNCH+r'\_build_windows.bat')
        self.assertEqual(len(changes),5)

    def test_whole_prefix_only_and_case_insensitive(self):
        self.assertEqual(m.convert_path(r'f:\frb\TOOLS\FRB_LAUNCH\a.bat',launch_home='Z:\\New',studio_home='Z:\\Studio',symbolic=True),r'%launch_home%\a.bat')
        self.assertEqual(m.convert_path(m.LEGACY_LAUNCH+'Backup',launch_home='a',studio_home='b',symbolic=True),m.LEGACY_LAUNCH+'Backup')
        self.assertEqual(m.convert_path(r'F:\FRB\data\abc.md',launch_home='a',studio_home='b',symbolic=True),r'F:\FRB\data\abc.md')

    @mock.patch.object(m, 'app_is_running', return_value=False)
    def test_invalid_json_has_no_side_effect(self, _):
        (self.home/m.LIVE_CONFIG).write_text('{bad',encoding='utf-8')
        self.assertEqual(m.main(['--home',str(self.home),'--apply']),1)
        self.assertFalse((self.home/'backups').exists())

    def test_invalid_model_has_no_side_effect(self):
        data=copy.deepcopy(self.original)
        data['items'][0]['page_id']='invalid'
        (self.home/m.LIVE_CONFIG).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        self.assertEqual(m.main(['--home',str(self.home),'--apply']),1)
        self.assertFalse((self.home/'backups').exists())

    def test_dump_json_retains_utf8_and_bom(self):
        raw=b'\xef\xbb\xbf'+b'{"hello":"a"}\r\n'
        target=m.dump_json(raw,{'hello':'日本語'})
        self.assertTrue(target.startswith(b'\xef\xbb\xbf'))
        self.assertIn('日本語'.encode('utf-8'),target)
        self.assertIn(b'\r\n',target)

    def test_generated_action_paths_are_supported_by_expander(self):
        import sys
        sys.path.insert(0,str(ROOT/'src'))
        from core import Expander
        values={'launch_home':str(self.home),'studio_root':str(self.home.parent/'FRB_Studio')}
        data={'launch_variables':[], 'launch_timezone':'Asia/Tokyo'}
        converted,_=m.migrate_data(self.original,launch_home=str(self.home),studio_home=values['studio_root'])
        expanded=Expander(data,values=values)
        launch=converted['items'][0]['launch_actions'][0]['launch_target']
        studio=converted['items'][1]['launch_browse_target']
        self.assertEqual(expanded.expand(launch),str(self.home)+r'\_build_windows.bat')
        self.assertEqual(expanded.expand(studio),values['studio_root']+r'\data\json')
        sys.path.pop(0)


if __name__ == '__main__':
    unittest.main()
