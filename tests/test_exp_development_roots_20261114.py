"""Paths edited in source are independent of an update-test install root."""
from __future__ import annotations
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from core import Expander
from source_studio_path import editor_studio_root
from repair_exp_development_roots import plan_repair


def source():
    return json.loads((ROOT/'defaults/frb_launch_data.template.json').read_text('utf-8'))


def test_exp_roots_do_not_follow_test_install():
    data = source()
    ex = Expander(data, values={'launch_home':r'F:\FRB_Update_Test\FRBLaunch',
                                'studio_root':r'F:\FRB_Update_Test\FRBLaunch\Studio'})
    items = {row['item_id']:row for row in data['items']}
    launch = items['3602dda2-b6e9-4a04-859e-56de69037470']
    studio = items['studio_dir']
    assert ex.expand(launch['launch_browse_target']) == r'F:\FRB_Apps\FRB_Launch'
    assert ex.expand(studio['launch_browse_target']) == r'F:\FRB_Apps\FRB_Studio'
    assert ex.expand(studio['launch_actions'][0]['launch_target']) == r'F:\FRB_Apps\FRB_Studio'


def test_studio_editor_prefers_explicit_source_exe(tmp_path):
    root = tmp_path / 'source_studio'
    exe = root / 'NativeShell/_publish/FRBStudio.NativeShell.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'test')
    doc = {'launch_variables':[dict(variable_id='studio_source_root', launch_variable_type='literal',launch_value=str(root))]}
    assert editor_studio_root(doc, 'bundled_studio') == str(root.resolve())
    exe.unlink()
    assert editor_studio_root(doc, 'bundled_studio') == 'bundled_studio'


def test_one_time_repair_changes_only_named_source_entries():
    data = source()
    original = copy.deepcopy(data)
    for row in data['items']:
        if row.get('item_id')=='studio_dir':
            row['launch_browse_target']='%studio_root%'
            row['launch_actions'][0]['launch_target']='%studio_root%'
        if row.get('item_id')=='3602dda2-b6e9-4a04-859e-56de69037470':
            row['launch_browse_target']='%launch_home%'
            row['launch_actions'][0]['launch_target']='%launch_home%'
    changes = plan_repair(data,r'F:\FRB_Apps\FRB_Launch',r'F:\FRB_Apps\FRB_Studio')
    assert changes
    items = {r['item_id']:r for r in data['items']}
    assert items['studio_dir']['launch_browse_target']=='%studio_source_root%'
    assert items['3602dda2-b6e9-4a04-859e-56de69037470']['launch_browse_target']=='%launch_source_root%'
    original_other = {r['item_id']:r for r in original['items'] if r['item_id'] not in ('studio_dir','3602dda2-b6e9-4a04-859e-56de69037470')}
    assert {r['item_id']:r for r in data['items'] if r['item_id'] in original_other} == original_other
    second=copy.deepcopy(data)
    assert plan_repair(second,r'F:\FRB_Apps\FRB_Launch',r'F:\FRB_Apps\FRB_Studio') == []


def test_repair_preserves_custom_user_source_variable():
    data=source()
    v=next(x for x in data['launch_variables'] if x['variable_id']=='studio_source_root')
    v['launch_value']=r'G:\custom\Studio'
    plan_repair(data,r'F:\FRB_Apps\FRB_Launch',r'F:\FRB_Apps\FRB_Studio')
    assert v['launch_value']==r'G:\custom\Studio'


def test_one_time_script_backs_up_original_and_updates_user_config(tmp_path):
    from repair_exp_development_roots import main
    data=source()
    item=next(row for row in data['items'] if row['item_id']=='studio_dir')
    item['launch_browse_target']='%studio_root%'
    cfg=tmp_path/'UserData/frb_launch_data.json'
    cfg.parent.mkdir()
    original=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    cfg.write_bytes(original)
    assert main(['--data',str(cfg),'--launch-root',str(tmp_path/'Launch'),'--studio-root',str(tmp_path/'Studio'),'--dry-run'])==0
    assert cfg.read_bytes()==original
    assert main(['--data',str(cfg),'--launch-root',str(tmp_path/'Launch'),'--studio-root',str(tmp_path/'Studio')])==0
    assert next(row for row in json.loads(cfg.read_text('utf-8'))['items'] if row['item_id']=='studio_dir')['launch_browse_target']=='%studio_source_root%'
    assert next((cfg.parent/'_Backups').glob('*.json')).read_bytes()==original
