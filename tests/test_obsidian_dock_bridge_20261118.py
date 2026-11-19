"""Obsidian third-column CLI experiment: no plugin or vault mutations.

The mock JS runtime exercises popout-only binding, idempotent sidebar collapse,
and in-place leaf switching. Real Windows/Electron still requires acceptance.
"""
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from obsidian_dock_bridge import (bind_code, switch_code, cli_eval,
                                  find_cli, registered_note)


ROOT = Path(__file__).resolve().parents[1]
PANEL = (ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')


def _node(script, *, scenario='normal'):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js required for mock Obsidian JS runtime')
    mock = r'''
      const window={name:'main'};
      const events=[];
      const dock={width:270, classList:{contains:()=>false},
          getBoundingClientRect(){return {width:this.width}}};
      const toggle={click(){events.push('toggle');dock.width=0}};
      const doc={defaultView:{name:'popout'},
          querySelector(selector){return selector.includes('workspace-split')?dock:toggle}};
      let target={path:'FRB/釣り メモ.md',extension:'md'};
      const leaf={view:{file:target,containerEl:{ownerDocument:doc}},
          openFile:async file=>{events.push('open:'+file.path);leaf.view.file=file}};
      const mainLeaf={view:{file:target,containerEl:{ownerDocument:{defaultView:window}}}};
      const app={workspace:{getLeavesOfType:()=>[leaf,mainLeaf]},
          vault:{getAbstractFileByPath:path=>path==='FRB/次の実験.md'?{path,extension:'md'}:null}};
    '''
    if scenario == 'ambiguous':
        mock += '''app.workspace.getLeavesOfType=()=>[leaf,{view:{file:target,containerEl:{ownerDocument:doc}}}];\n'''
    if scenario == 'collapsed':
        mock += "dock.width=0;\n"
    mock += ("Promise.resolve(eval(" + json.dumps(script, ensure_ascii=False) + "))"
             ".then(result=>console.log(JSON.stringify({result,events,token:leaf.__frbLaunchDockToken||null,file:leaf.view.file.path})))"
             ".catch(e=>{console.error(e);process.exit(1)})")
    return json.loads(subprocess.check_output([node, '-e', mock], text=True, timeout=5))


def test_register_popout_only_and_collapse_sidebar():
    obj = _node(bind_code('FRB/釣り メモ.md', 'dock123'))
    assert obj['result'] == 'FRB_BOUND'
    assert obj['token'] == 'dock123'
    assert obj['events'] == ['toggle']


def test_register_does_not_expand_collapsed_sidebar():
    obj = _node(bind_code('FRB/釣り メモ.md', 'dock123'), scenario='collapsed')
    assert obj['result'] == 'FRB_BOUND'
    assert obj['events'] == []


def test_ambiguous_popout_must_not_be_tagged_or_toggled():
    obj = _node(bind_code('FRB/釣り メモ.md', 'dock123'), scenario='ambiguous')
    assert obj['result'] == 'FRB_NOT_UNIQUE'
    assert obj['token'] is None
    assert obj['events'] == []


def test_reuse_leaf_opens_new_file_without_new_window():
    script = bind_code('FRB/釣り メモ.md', 'dock123') + ';' + switch_code('FRB/次の実験.md','dock123')
    obj = _node(script)
    assert obj['result'] == 'FRB_SWITCHED'
    assert obj['file'] == 'FRB/次の実験.md'
    assert obj['events'] == ['toggle', 'open:FRB/次の実験.md']


def test_missing_file_must_not_replace_open_document():
    script = bind_code('FRB/釣り メモ.md', 'dock123') + ';' + switch_code('FRB/存在しない.md','dock123')
    obj = _node(script)
    assert obj['result'] == 'FRB_NOT_FOUND'
    assert obj['file'] == 'FRB/釣り メモ.md'
    assert obj['events'] == ['toggle']


def test_token_scope_prevents_operating_unregistered_popup():
    obj = _node(switch_code('FRB/次の実験.md','wrongToken'))
    assert obj['result'] == 'FRB_NOT_BOUND'
    assert obj['events'] == []


def test_cli_eval_success_and_failure_are_fail_closed():
    def fake_ok(command, **kw):
        assert command[:3] == ['C:/Obsidian.com', 'vault=abc', 'eval']
        assert command[3].startswith('code=')
        assert kw['timeout'] == 5 and kw['capture_output']
        return SimpleNamespace(returncode=0, stdout='FRB_SWITCHED\n', stderr='')
    assert cli_eval('abc', '1+1', executable='C:/Obsidian.com', runner=fake_ok) == 'FRB_SWITCHED'
    def fake_prefix(*_, **__):
        return SimpleNamespace(returncode=0, stdout='=> FRB_BOUND\n', stderr='')
    assert cli_eval('abc', '1+1', executable='C:/Obsidian.com', runner=fake_prefix) == 'FRB_BOUND'
    def fake_ambiguous(*_, **__):
        return SimpleNamespace(returncode=0, stdout='=> FRB_BOUND\n=> FRB_SWITCHED\n', stderr='')
    assert cli_eval('abc', '1+1', executable='C:/Obsidian.com', runner=fake_ambiguous) == 'FRB_CLI_FAILED' 
    def fake_error(*_, **__):
        return SimpleNamespace(returncode=0, stdout='done', stderr='')
    assert cli_eval('abc', '1+1', executable='C:/Obsidian.com', runner=fake_error) == 'FRB_CLI_FAILED'
    def fake_crash(*_, **__):
        raise subprocess.TimeoutExpired('obsidian', 5)
    assert cli_eval('abc', '1+1', executable='C:/Obsidian.com', runner=fake_crash) == 'FRB_CLI_FAILED'
    assert cli_eval('abc', '1+1', executable=None, runner=None) in ('FRB_NO_CLI', 'FRB_CLI_FAILED')


def test_cli_override_never_falls_back_to_unrelated_executable(tmp_path, monkeypatch):
    exe=tmp_path/'Obsidian.com'
    exe.write_text('cli', encoding='utf-8')
    monkeypatch.setenv('FRB_LAUNCH_OBSIDIAN_CLI', str(exe))
    assert find_cli() == str(exe)
    monkeypatch.setenv('FRB_LAUNCH_OBSIDIAN_CLI', str(tmp_path/'not-there.com'))
    assert find_cli() is None


def test_register_vault_path_resolved_without_modifying_config(tmp_path, monkeypatch):
    import external_preview_route as route
    root=tmp_path/'My Vault'
    root.mkdir()
    (root/'sub').mkdir()
    note=root/'sub'/'FRB テスト.md'
    note.write_text('# test', encoding='utf-8')
    registry=tmp_path/'obsidian.json'
    registry.write_text(json.dumps({'vaults':{'vault-id':{'path':str(root)}}}),encoding='utf-8')
    monkeypatch.setattr(route, '_obsidian_vault_registry_path', lambda: registry)
    before=registry.read_bytes()
    assert registered_note(str(note)) == ('vault-id', 'sub/FRB テスト.md')
    assert registry.read_bytes() == before


def test_panel_attempts_reuse_before_parking_and_keeps_sakura_separate():
    target = PANEL.split('    def open_external(self, target):',1)[1].split('    def sakura_attached(self):',1)[0]
    assert target.index('self._switch_obsidian_inside(target)') < target.index('self._park_current()')
    assert "if target.app == 'obsidian':" in target
    assert 'self._begin_obsidian_cli_bind(target, hwnd)' in PANEL
    assert 'self._obsidian_cli_token != token' in PANEL
    assert 'self._obsidian_cli_queued = target' in PANEL
    assert '.terminate(' not in PANEL and '.kill(' not in PANEL
