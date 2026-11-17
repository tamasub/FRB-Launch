"""FRB Launch owned Studio session: no per-JSON process and no stale target."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SRC = Path(__file__).resolve().parents[1] / 'src' / 'studio_preview_panel.py'


def method(name, **globals_):
    tree = ast.parse(SRC.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'StudioPreviewPanel')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    code = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(SRC), 'exec')
    scope = {'Path': Path, **globals_}
    exec(code, scope)
    return scope[name]


def panel_stub(previous):
    calls = []
    process = NS(poll=lambda: None)
    attached = NS(resize=lambda *a: calls.append(('resize', a)))
    panel = NS(
        content_stack=NS(setCurrentWidget=lambda *_: None), host=NS(width=lambda: 550, height=lambda: 480),
        _process=process, _target=previous, _external_key=None, _attached=attached,
        _launch_pipe_token='1234567890abcdef1234567890abcdef', _parked={},
        _timer=NS(start=lambda: None), _started=0,
        _park_current=lambda: calls.append(('park',)),
        _show_target_title=lambda target: calls.append(('title', target)),
        _switch_launch_document=lambda target: calls.append(('switch', target)) or True,
        status_label=NS(setText=lambda *_: None, show=lambda: None, hide=lambda: None),
    )
    return panel, calls


def test_same_file_doubleclick_reloads_in_existing_process():
    target = ('C:/FRB/incident.json', 'studio.exe', 'C:/FRB')
    panel, calls = panel_stub(target)
    assert method('open_document')(panel, target)
    assert ('switch', target) in calls
    assert ('park',) not in calls


def test_other_file_switches_without_parking_or_forking():
    original = ('C:/FRB/incident.json', 'studio.exe', 'C:/FRB')
    different = ('C:/FRB/another.json', 'studio.exe', 'C:/FRB')
    panel, calls = panel_stub(original)
    assert method('open_document')(panel, different)
    assert ('switch', different) in calls
    assert panel._target == original  # Switch ACK owns target mutation.
    assert ('park',) not in calls


def test_switch_cancellation_keeps_original_target():
    previous = ('C:/FRB/first.json', 'studio.exe', 'C:/FRB')
    requested = ('C:/FRB/second.json', 'studio.exe', 'C:/FRB')
    panel, calls = panel_stub(previous)
    panel._launch_switch_pending = requested
    method('_on_launch_switch_completed')(panel, requested, 'CANCEL')
    assert panel._target == previous
    assert panel._launch_switch_pending is None
    assert ('title', requested) not in calls


def test_switch_acceptance_updates_target_only_after_studio_ack():
    previous = ('C:/FRB/first.json', 'studio.exe', 'C:/FRB')
    requested = ('C:/FRB/second.json', 'studio.exe', 'C:/FRB')
    panel, calls = panel_stub(previous)
    panel._launch_switch_pending = requested
    method('_on_launch_switch_completed')(panel, requested, 'OK')
    assert panel._target == requested
    assert ('title', requested) in calls


def test_preview_startup_passes_private_pipe_and_no_splash(monkeypatch):
    old = ('C:/FRB/first.json', 'studio.exe', 'C:/FRB')
    panel, calls = panel_stub(None)
    panel._process = None
    panel._attached = None
    captured = []
    class Popen:
        def __init__(self, args, cwd):
            captured.append((args, cwd))
    stubsubprocess = NS(Popen=Popen)
    uuid = NS(uuid4=lambda: NS(hex='a' * 32))
    fn = method('open_document', subprocess=stubsubprocess, uuid=uuid,
                os=NS(getpid=lambda: 43210),
                studio_start_command=lambda t: ([t[1], '--open-json=' + t[0]], t[2]),
                time=NS(monotonic=lambda: 1))
    assert fn(panel, old)
    assert captured == [(['studio.exe', '--open-json=C:/FRB/first.json',
                          '--launch-preview', '--launch-preview-pipe=' + 'a' * 32,
                          '--launch-preview-owner-pid=43210'], 'C:/FRB')]
