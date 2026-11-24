"""Default-on native tab group hint with conservative HWND guard.

These are AST-extracted request-path tests, not Windows desktop UI tests.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from external_preview_route import ExternalPreviewTarget, external_start_command
from sakura_guest_bridge import active_group_trial_enabled, active_group_trial_safe
import external_win32_host


def _open_sakura_guest_method(calls):
    code = (ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
    tree = ast.parse(code)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'StudioPreviewPanel')
    meth = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == '_open_sakura_guest')
    ns = dict(Path=Path, time=NS(monotonic=lambda: 42),
              subprocess=NS(Popen=lambda cmd, **kw: calls.append((cmd, kw))))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[meth], type_ignores=[])),
                 str(ROOT / 'src/studio_preview_panel.py'), 'exec'), ns)
    return ns['_open_sakura_guest']


def _panel(calls, *, parked=None, ejected=()):
    attached = NS(hwnd=101, attached=True,
                  resize=lambda w, h: calls.append(('resize', w, h)))
    key=('sakura','c:/docs/001.txt')
    status=NS(setText=lambda s: calls.append(('status', s)),
              show=lambda: calls.append(('status_show',)))
    panel=NS(_external_pending=None, _sakura_guest_switch=None,
             _attached=attached, _external_key=key,
             _sakura_guest_queued=None, _external_parked=parked or {},
             _auto_ejected_keys=set(ejected),
             _restore_known_sakura_guest=lambda target: False,
             _external_timer=NS(start=lambda: calls.append(('timer',))),
             _sakura_trace=lambda *a, **kw: calls.append(('trace', a[0], kw)),
             status_label=status,
             host=NS(width=lambda: 640, height=lambda: 580))
    return panel


def _target():
    return ExternalPreviewTarget('sakura', 'C:/docs/002.txt', 'C:/Sakura/sakura.exe')


def test_active_group_hint_default_on_but_explicitly_disableable():
    assert active_group_trial_enabled({})
    assert active_group_trial_enabled({'FRB_SAKURA_ACTIVE_GROUP_TRIAL':'1'})
    for value in ('0', 'off', 'false', 'no'):
        assert not active_group_trial_enabled({'FRB_SAKURA_ACTIVE_GROUP_TRIAL': value})
    target=_target()
    assert external_start_command(target)==[
        'C:/Sakura/sakura.exe','--','C:/docs/002.txt']
    assert external_start_command(target, active_group=True)==[
        'C:/Sakura/sakura.exe','-GROUP=0','--','C:/docs/002.txt']
    assert '--' in external_start_command(target, active_group=True)


def test_only_managed_visible_hwnds_and_no_explicit_popout_qualify():
    windows=[(101,1200,'001.txt'),(202,1300,'002.txt')]
    key=('sakura', 'c:/docs/001.txt')
    parked={('sakura','c:/docs/002.txt'):202}
    assert active_group_trial_safe(101,windows,parked)
    assert not active_group_trial_safe(101,windows,{},())
    assert not active_group_trial_safe(101,windows,parked,{key})
    assert not active_group_trial_safe(101,[(202,1300,'002.txt')],parked)


def test_existing_docked_editor_opt_in_requests_active_group(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_SAKURA_ACTIVE_GROUP_TRIAL', '1')
    monkeypatch.setattr(external_win32_host, 'snapshot_editor_windows', lambda app: frozenset({101}))
    monkeypatch.setattr(external_win32_host, 'editor_windows',
                        lambda app, include_hidden=False: [(101,1200,'001.txt')])
    calls=[]
    panel=_panel(calls)
    assert _open_sakura_guest_method(calls)(panel,_target()) is True
    assert panel._attached.hwnd==101 and panel._attached.attached
    assert panel._sakura_guest_switch[0].path=='C:/docs/002.txt'
    assert [c[0] for c in calls if isinstance(c,tuple) and isinstance(c[0],list)]==[
        ['C:/Sakura/sakura.exe','-GROUP=0','--','C:/docs/002.txt']]


def test_unmanaged_visible_sakura_forces_original_open(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_SAKURA_ACTIVE_GROUP_TRIAL', '1')
    monkeypatch.setattr(external_win32_host, 'snapshot_editor_windows', lambda app: frozenset({101,303}))
    monkeypatch.setattr(external_win32_host, 'editor_windows',
                        lambda app, include_hidden=False: [(101,1200,'001.txt'), (303,1400,'private.txt')])
    calls=[]
    assert _open_sakura_guest_method(calls)(_panel(calls), _target())
    assert [c[0] for c in calls if isinstance(c,tuple) and isinstance(c[0],list)]==[
        ['C:/Sakura/sakura.exe','--','C:/docs/002.txt']]
    assert any(c[0]=='trace' and c[1]=='ACTIVE_GROUP_TRIAL_REQUEST'
               and c[2]['enabled'] is False for c in calls)


def test_explicitly_ejected_sakura_forces_original_open(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_SAKURA_ACTIVE_GROUP_TRIAL', '1')
    monkeypatch.setattr(external_win32_host, 'snapshot_editor_windows', lambda app: frozenset({101,303}))
    monkeypatch.setattr(external_win32_host, 'editor_windows',
                        lambda app, include_hidden=False: [(101,1200,'001.txt'), (303,1300,'old.txt')])
    calls=[]
    old=('sakura','c:/docs/old.txt')
    panel=_panel(calls, parked={old:303}, ejected={old})
    assert _open_sakura_guest_method(calls)(panel, _target())
    assert [c[0] for c in calls if isinstance(c,tuple) and isinstance(c[0],list)]==[
        ['C:/Sakura/sakura.exe','--','C:/docs/002.txt']]


def test_default_mode_uses_group_only_for_verified_attached_editor(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    monkeypatch.delenv('FRB_SAKURA_ACTIVE_GROUP_TRIAL', raising=False)
    monkeypatch.setattr(external_win32_host, 'snapshot_editor_windows', lambda app: frozenset({101}))
    monkeypatch.setattr(external_win32_host, 'editor_windows',
                        lambda *a, **k: [(101,1200,'001.txt')])
    calls=[]
    assert _open_sakura_guest_method(calls)(_panel(calls), _target())
    assert [c[0] for c in calls if isinstance(c,tuple) and isinstance(c[0],list)]==[
        ['C:/Sakura/sakura.exe','-GROUP=0','--','C:/docs/002.txt']]


def test_explicit_group_disable_uses_original_open_without_probe(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_SAKURA_ACTIVE_GROUP_TRIAL', '0')
    monkeypatch.setattr(external_win32_host, 'snapshot_editor_windows', lambda app: frozenset({101}))
    monkeypatch.setattr(external_win32_host, 'editor_windows',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('disabled group probe')))
    calls=[]
    assert _open_sakura_guest_method(calls)(_panel(calls), _target())
    assert [c[0] for c in calls if isinstance(c,tuple) and isinstance(c[0],list)]==[
        ['C:/Sakura/sakura.exe','--','C:/docs/002.txt']]


def test_trial_bat_preserves_prior_minimize_parking_and_does_not_edit_settings():
    script=(ROOT/'trial_sakura_active_group.bat').read_text(encoding='utf-8')
    assert 'FRB_SAKURA_ACTIVE_GROUP_TRIAL=1' in script
    assert 'FRB_SAKURA_PARK_MODE=minimize' in script
    assert 'src\\app.py' in script
    assert 'state.ini' not in script


def test_reopening_current_file_does_not_issue_any_native_command(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_SAKURA_ACTIVE_GROUP_TRIAL', '1')
    calls=[]
    panel=_panel(calls)
    target=ExternalPreviewTarget('sakura','C:/docs/001.txt','C:/Sakura/sakura.exe')
    assert _open_sakura_guest_method(calls)(panel,target) is True
    assert ('resize',640,580) in calls
    assert not any(isinstance(c,tuple) and isinstance(c[0],list) for c in calls)
