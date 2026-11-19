"""Main-window Obsidian docking contract (Linux-friendly mocks + real JS in Node).

These tests deliberately do not claim real Windows/Electron verification.
"""
import ast
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from external_preview_route import obsidian_open_uri, ExternalPreviewTarget
from obsidian_dock_bridge import (
    main_probe_code, bind_main_code, switch_main_code,
    main_window_matches_caption, cli_eval,
)

SRC = Path(__file__).resolve().parents[1] / 'src'
SOURCE = (SRC/'studio_preview_panel.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
             and n.name == 'StudioPreviewPanel')


class Timer:
    def __init__(self): self.stopped = False
    def stop(self): self.stopped = True
    def start(self): self.stopped = False


class Status:
    def __init__(self): self.text=''; self.visible=False
    def setText(self, x): self.text=x
    def show(self): self.visible=True
    def hide(self): self.visible=False


class Attached:
    def __init__(self, hwnd, host):
        self.hwnd = hwnd
        self.attached = True
        self.host = host
        self.resized = []
        self.detached = []
    def resize(self, w, h): self.resized.append((w,h))
    def detach(self, **kwargs): self.detached.append(kwargs)


class QTimerFake:
    delayed = []
    @classmethod
    def singleShot(cls, delay, callback): cls.delayed.append((delay, callback))


def method(name):
    node = next(x for x in CLASS.body if isinstance(x, ast.FunctionDef) and x.name==name)
    scope = {'time': time, 'QTimer': QTimerFake}
    exec(compile(ast.Module(body=[node], type_ignores=[]), name, 'exec'), scope)
    return scope[name]


def eval_js(script, *, main=True, existing=True, exact=True):
    node=shutil.which('node')
    if not node: pytest.skip('Node.js is needed to simulate Obsidian API')
    mock = r'''
      const window={name:'main'};
      const events=[];
      const document={title:'Main Obsidian Window'};
      let current={path:'FRB/A.md',extension:'md'};
      const noteB={path:'FRB/B.md',extension:'md'};
      const mainDocument={defaultView:window,title:'Main Obsidian Window'};
      const popupDocument={defaultView:{name:'popup'}};
      let mainLeaf={view:{file:current,containerEl:{ownerDocument:mainDocument}},
          getViewState:()=>({type:'markdown'}),
          openFile:async file=>{events.push('main:'+file.path);mainLeaf.view.file=file}};
      const popupLeaf={view:{file:current,containerEl:{ownerDocument:popupDocument}},
          getViewState:()=>({type:'markdown'}),
          openFile:async file=>{events.push('popup:'+file.path);popupLeaf.view.file=file}};
      let collapsed=false;
      const app={workspace:{
          iterateRootLeaves: fn=>{if(MAIN)fn(mainLeaf);fn(popupLeaf)},
          getLeavesOfType:()=>MAIN?[popupLeaf,mainLeaf]:[popupLeaf],
          leftSplit:{collapse:()=>{events.push('collapse');collapsed=true}}
          },vault:{getAbstractFileByPath:path=>{
          if(path==='FRB/A.md')return {path,extension:'md'};
          if(path==='FRB/B.md')return noteB;
          return null}}};
    '''.replace('MAIN','true' if main else 'false')
    mock += ('Promise.resolve(eval('+json.dumps(script,ensure_ascii=False)+'))'
             '.then(result=>console.log(JSON.stringify({result,events,collapsed,mainFile:mainLeaf.view.file.path,popupFile:popupLeaf.view.file.path,token:mainLeaf.__frbLaunchDockToken||null})))'
             '.catch(e=>{console.error(e);process.exit(2)})')
    return json.loads(subprocess.check_output([node,'-e',mock],text=True,timeout=6))


def test_main_probe_reuses_main_leaf_and_never_opens_popup():
    result=eval_js(main_probe_code('FRB/B.md'))
    assert result['result']=='FRB_MAIN_TITLE:Main%20Obsidian%20Window'
    assert result['events']==['main:FRB/B.md']
    assert result['mainFile']=='FRB/B.md' and result['popupFile']=='FRB/A.md'


def test_main_probe_rejects_popup_only_without_mutation():
    result=eval_js(main_probe_code('FRB/B.md'),main=False)
    assert result['result']=='FRB_MAIN_NOT_READY'
    assert result['events']==[]


def test_main_bind_closes_sidebar_then_switches_same_leaf():
    js = (bind_main_code('FRB/A.md','session1') + ';' +
          switch_main_code('FRB/B.md','session1'))
    result=eval_js(js)
    assert result['result']=='FRB_SWITCHED'
    assert result['token']=='session1'
    assert result['mainFile']=='FRB/B.md' and result['popupFile']=='FRB/A.md'
    assert result['events']==['collapse','main:FRB/B.md','collapse']


def test_main_only_tag_does_not_bind_popout():
    result=eval_js(bind_main_code('FRB/A.md','session1'),main=False)
    assert result['result']=='FRB_NOT_UNIQUE'
    assert result['events']==[]


def test_wrong_token_cannot_switch_main():
    result=eval_js(switch_main_code('FRB/B.md','invalid'))
    assert result['result']=='FRB_NOT_BOUND' and result['events']==[]


def test_nonexistent_note_preserves_current_main():
    result=eval_js(main_probe_code('FRB/not-exist.md'))
    assert result['result']=='FRB_NOT_FOUND' and result['events']==[]


def test_hwnd_matching_requires_unique_exact_title_and_real_obsidian_pid():
    windows=[(77,22,'Main Obsidian Window'),(88,23,'Main Obsidian Window (copy)')]
    assert main_window_matches_caption('Main Obsidian Window',windows)==77
    assert main_window_matches_caption('Other Window',windows) is None
    assert main_window_matches_caption('Main Obsidian Window',windows+[(99,24,'Main Obsidian Window')]) is None
    assert main_window_matches_caption('',windows) is None


def test_cli_eval_accepts_encoded_native_caption_only():
    runner=lambda *_args,**kw:SimpleNamespace(returncode=0,stdout='=> FRB_MAIN_TITLE:My%20Vault\n')
    assert cli_eval('vault','code',executable='obsidian.com',runner=runner)=='FRB_MAIN_TITLE:My%20Vault'
    runner=lambda *_args,**kw:SimpleNamespace(returncode=0,stdout='FRB_MAIN_NOT_READY\n')
    assert cli_eval('vault','code',executable='obsidian.com',runner=runner)=='FRB_MAIN_NOT_READY'


def test_obsidian_uri_never_specifies_popout():
    assert 'paneType=window' not in obsidian_open_uri(r'F:\\Vault\\note.md')
    assert 'paneType=window' not in (SRC/'external_preview_route.py').read_text(encoding='utf-8')


def fresh_panel():
    target=ExternalPreviewTarget('obsidian','C:/vault/A.md')
    obj=SimpleNamespace(
        _external_pending=(target,frozenset(),None,time.monotonic()),
        _external_key=target.key,
        _external_timer=Timer(),
        _obsidian_main_probe_token='main-session',
        _obsidian_main_probe_busy=True,
        _obsidian_main_probe_attempts=1,
        _obsidian_cli_queued=None,
        _attached=None,
        host=SimpleNamespace(winId=lambda:99,width=lambda:560,height=lambda:800),
        status_label=Status(),
        title_label=SimpleNamespace(setText=lambda s:None,setToolTip=lambda s:None),
        launcher=SimpleNamespace(isVisible=lambda:False),
        _sync_popout_button=lambda:None,
        _begin_obsidian_cli_bind=lambda file,hwnd:True,
    )
    obj._fail_obsidian_main_dock=lambda reason:method('_fail_obsidian_main_dock')(obj,reason)
    return obj,target


def test_main_window_positive_handshake_docks_only_unique_hwnd(monkeypatch):
    import external_win32_host, studio_win32_host, embedded_obsidian_presentation
    obj,target=fresh_panel()
    attached=[]
    monkeypatch.setattr(external_win32_host,'editor_windows',lambda *a,**k:[(70,15,'My Obsidian')])
    monkeypatch.setattr(studio_win32_host,'AttachedStudioWindow',lambda hwnd,host:attached.append(Attached(hwnd,host)) or attached[-1])
    monkeypatch.setattr(embedded_obsidian_presentation,'prefer_light_native_frame',lambda hwnd:None)
    method('_on_obsidian_main_probe_completed')(obj,'main-session',target,'FRB_MAIN_TITLE:My%20Obsidian')
    assert len(attached)==1 and attached[0].hwnd==70 and attached[0].host==99
    assert attached[0].resized==[(560,800)]
    assert obj._external_pending is None
    assert obj._external_key==target.key
    assert obj._obsidian_main_probe_token is None
    assert obj._external_timer.stopped


def test_old_probe_result_cannot_take_over_new_session(monkeypatch):
    import external_win32_host
    obj,target=fresh_panel()
    monkeypatch.setattr(external_win32_host,'editor_windows',lambda *a,**k:(_ for _ in ()).throw(AssertionError('must not scan')))
    method('_on_obsidian_main_probe_completed')(obj,'stale-session',target,'FRB_MAIN_TITLE:My%20Obsidian')
    assert obj._attached is None and obj._external_pending[0]==target


def test_close_of_embedded_main_restores_window_without_wm_close(monkeypatch):
    import studio_win32_host
    obj,target=fresh_panel()
    actual=Attached(88,99)
    obj._attached=actual
    obj._external_key=target.key
    obj._external_pending=None
    obj._external_parked={}
    obj._sakura_switch_from=None
    obj._reset_obsidian_cli=lambda:None
    monkeypatch.setattr(studio_win32_host,'request_editor_window_close',lambda *_:(_ for _ in ()).throw(AssertionError('must not terminate borrowed Obsidian')))
    assert method('close_external_editors')(obj)
    assert actual.detached==[{'foreground':False,'show_window':True}]
    assert obj._external_key is None


def test_explicit_timeout_does_not_close_existing_main():
    obj,target=fresh_panel()
    assert method('_fail_obsidian_main_dock')(obj,'window ambiguous') is None
    assert obj._external_pending is None and obj._obsidian_main_probe_token is None
    assert 'window ambiguous' in obj.status_label.text
