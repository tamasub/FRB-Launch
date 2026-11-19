"""Cold-launch Obsidian 1.15.1 CLI readiness gate, without a Windows desktop.

The real CLI can return exit 0 with `Command "eval" not found` while booting.
The panel must not consume its one-time note open until an eval succeeds.
"""
import ast
import json
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace, MethodType

import pytest

import obsidian_dock_bridge as bridge
import obsidian_dock_trace as trace_module
from external_preview_route import ExternalPreviewTarget

SRC = Path(__file__).resolve().parents[1] / 'src'
SOURCE = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
CLASS = next(node for node in ast.parse(SOURCE).body
             if isinstance(node, ast.ClassDef) and node.name == 'StudioPreviewPanel')


class InlineThread:
    def __init__(self, target, **kwargs):
        self.target = target
    def start(self):
        self.target()


class Timers:
    actions = []
    @classmethod
    def singleShot(cls, wait, callback):
        cls.actions.append((wait, callback))


class Timer:
    def __init__(self): self.stopped = False
    def stop(self): self.stopped = True


class Label:
    def __init__(self): self.text = ''; self.visible = False
    def setText(self, value): self.text = value
    def setToolTip(self, value): self.tooltip = value
    def show(self): self.visible = True
    def hide(self): self.visible = False


class Attached:
    def __init__(self, hwnd, host):
        self.hwnd = hwnd
        self.host = host
        self.attached = True
    def resize(self, width, height):
        self.size = (width, height)


def extracted(name):
    node = next(x for x in CLASS.body
                if isinstance(x, ast.FunctionDef) and x.name == name)
    namespace = {'QTimer': Timers, 'threading': SimpleNamespace(Thread=InlineThread),
                 'time': time}
    exec(compile(ast.Module(body=[node], type_ignores=[]), name, 'exec'), namespace)
    return namespace[name]


def test_cli_returncode_zero_eval_not_found_is_temporary_not_ready(monkeypatch):
    monkeypatch.setattr(trace_module, 'trace', lambda *a, **k: None)
    runner=lambda *a, **k: SimpleNamespace(returncode=0, stderr='',
        stdout='Error: Command "eval" not found. It may require a plugin to be enabled.\n')
    assert bridge.cli_eval('vault', "'FRB_CLI_READY'", executable='Obsidian.com',
                           runner=runner, stage='startup_ready') == 'FRB_CLI_NOT_READY'
    # The subprocess succeeded, but the application rejected the command.
    assert bridge.cli_eval('vault', "'FRB_CLI_READY'", executable='Obsidian.com',
        runner=lambda *a, **k: SimpleNamespace(returncode=0, stderr='',
                                                  stdout='=> FRB_CLI_READY\n')) == 'FRB_CLI_READY'


def test_ready_code_is_read_only_and_requires_main_root_workspace():
    code=bridge.main_ready_code()
    assert 'openFile(' not in code and '.collapse(' not in code
    assert 'newLeaf' not in code and 'paneType=window' not in code
    node=shutil.which('node')
    if not node:
        pytest.skip('Node.js not installed')
    for main, expected in [(True,'FRB_CLI_READY'),(False,'FRB_MAIN_NOT_READY')]:
        script='''const window={}; const app={workspace:{iterateRootLeaves:fn=>{
          if(%s)fn({view:{containerEl:{ownerDocument:{defaultView:window}}}});
        }}}; console.log(JSON.stringify(eval(%s)));''' % (
            'true' if main else 'false',json.dumps(code))
        reply=subprocess.check_output([node,'-e',script],text=True,timeout=5).strip()
        assert json.loads(reply)==expected


def test_specific_first_note_must_be_indexed_before_cli_can_open():
    # Main HWND and eval can be ready even before the requested note is indexed.
    code = bridge.main_ready_code('新しいMarkdown文書 (2).md')
    assert 'getAbstractFileByPath' in code
    assert '新しいMarkdown文書 (2).md' in code
    assert 'openFile(' not in code
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js not installed')
    for indexed, expected in [(False, 'FRB_MAIN_NOT_READY'),
                              (True, 'FRB_CLI_READY')]:
        script = ("const window={}; const app={"
                  "vault:{getAbstractFileByPath:path=>INDEXED?{extension:'md'}:null},"
                  "workspace:{iterateRootLeaves:fn=>{"
                  "fn({view:{containerEl:{ownerDocument:{defaultView:window}}}});"
                  "}}}; console.log(JSON.stringify(eval(CODE)));")
        script = script.replace('INDEXED', 'true' if indexed else 'false')
        script = script.replace('CODE', json.dumps(code))
        reply = subprocess.check_output([node, '-e', script], text=True, timeout=5).strip()
        assert json.loads(reply) == expected


def run_startup(monkeypatch, failures_before_ready, *, open_replies=None, verify_failures=0):
    import external_win32_host
    import studio_win32_host
    import embedded_obsidian_presentation

    Timers.actions=[]
    monkeypatch.setattr(trace_module, 'trace', lambda *args, **kw: None)
    monkeypatch.setattr(trace_module, 'trace_windows', lambda *args, **kw: None)
    monkeypatch.setattr(external_win32_host, 'editor_windows',
                        lambda *args, **kw: [(77,11,'Main Vault Window')])
    monkeypatch.setattr(studio_win32_host, 'AttachedStudioWindow', Attached)
    monkeypatch.setattr(embedded_obsidian_presentation,
                        'prefer_light_native_frame', lambda hwnd:None)
    monkeypatch.setattr(bridge,'registered_note',lambda path:('vault-id','note.md'))
    monkeypatch.setattr(bridge,'find_cli',lambda:'Obsidian.com')

    calls=[]
    def fake_eval(vault, js, **kwargs):
        stage=kwargs['stage']
        calls.append(stage)
        if stage=='startup_ready':
            return ('FRB_CLI_NOT_READY' if calls.count('startup_ready')<=failures_before_ready
                    else 'FRB_CLI_READY')
        if stage=='main_open':
            assert 'note.md' in js
            index=calls.count('main_open') - 1
            return (open_replies[index] if open_replies and index<len(open_replies)
                    else 'FRB_MAIN_OPENED')
        if stage=='main_verify':
            assert 'note.md' in js
            return ('FRB_MAIN_NOT_READY' if calls.count('main_verify')<=verify_failures
                    else 'FRB_MAIN_TITLE:Main%20Vault%20Window')
        raise AssertionError(stage)
    monkeypatch.setattr(bridge,'cli_eval',fake_eval)
    target=ExternalPreviewTarget('obsidian','C:/vault/note.md')
    panel=SimpleNamespace(
        _external_pending=(target,None,None,time.monotonic()),
        _external_key=target.key,
        _external_timer=Timer(),
        _obsidian_main_probe_token='session-1',
        _obsidian_main_probe_busy=False,
        _obsidian_main_probe_attempts=0,
        _obsidian_main_open_issued=False,
        _obsidian_cli_prepared=False,
        _obsidian_cli_queued=None,
        _attached=None,
        host=SimpleNamespace(winId=lambda:123,width=lambda:620,height=lambda:450),
        status_label=Label(), title_label=Label(),
        launcher=SimpleNamespace(isVisible=lambda:False),
        _sync_popout_button=lambda:None,
        _begin_obsidian_cli_bind=lambda target, hwnd:True,
    )
    probe=extracted('_probe_obsidian_main_window')
    completed=extracted('_on_obsidian_main_probe_completed')
    failed=extracted('_fail_obsidian_main_dock')
    panel._probe_obsidian_main_window=MethodType(probe,panel)
    panel._on_obsidian_main_probe_completed=MethodType(completed,panel)
    panel._fail_obsidian_main_dock=MethodType(failed,panel)
    panel._obsidian_main_probe_completed=SimpleNamespace(
        emit=lambda *args:panel._on_obsidian_main_probe_completed(*args))
    panel._probe_obsidian_main_window('session-1')
    for _ in range(45):
        if not Timers.actions: break
        _, fn=Timers.actions.pop(0)
        fn()
    assert not Timers.actions
    return panel,calls


def test_cold_start_waits_then_opens_note_once_and_attaches(monkeypatch):
    panel,calls=run_startup(monkeypatch,failures_before_ready=4)
    assert calls==['startup_ready']*5+['main_open','main_verify']
    assert panel._external_pending is None
    assert panel._attached.hwnd == 77
    assert panel._attached.size == (620,450)
    assert panel._obsidian_main_open_issued
    assert panel._external_timer.stopped


def test_never_ready_does_not_open_or_borrow_window(monkeypatch):
    panel,calls=run_startup(monkeypatch,failures_before_ready=100)
    assert calls==['startup_ready']*35
    assert 'main_open' not in calls and 'main_verify' not in calls
    assert panel._attached is None
    assert panel._external_pending is None
    assert panel._external_timer.stopped
    assert '準備完了' in panel.status_label.text


def test_first_note_open_ack_can_fail_but_verify_succeeds_without_duplicate(monkeypatch):
    panel,calls=run_startup(monkeypatch,failures_before_ready=1,
                            open_replies=['FRB_CLI_FAILED'])
    assert calls==['startup_ready','startup_ready','main_open','main_verify']
    assert panel._attached.hwnd==77
    assert calls.count('main_open')==1


def test_first_note_missing_after_open_is_retried_once_with_same_main_leaf(monkeypatch):
    panel,calls=run_startup(monkeypatch,failures_before_ready=0,
                            verify_failures=4)
    assert panel._attached.hwnd==77
    assert calls.count('main_open')==2
    assert calls.count('main_verify')==5
    assert panel._obsidian_main_reopen_count==1


def test_first_note_still_missing_after_retry_never_generates_extra_open_requests(monkeypatch):
    panel,calls=run_startup(monkeypatch,failures_before_ready=0,
                            verify_failures=100)
    assert panel._attached is None
    assert panel._external_pending is None
    assert calls.count('main_open')==2
    assert '準備完了' in panel.status_label.text


def test_first_note_cli_failure_is_bounded_to_two_open_attempts(monkeypatch):
    panel,calls=run_startup(monkeypatch,failures_before_ready=0,
                            open_replies=['FRB_CLI_NOT_READY','FRB_CLI_NOT_READY'],
                            verify_failures=100)
    assert panel._attached is None
    assert panel._external_pending is None
    assert calls.count('main_open')==2
    assert panel._obsidian_main_reopen_count==1
