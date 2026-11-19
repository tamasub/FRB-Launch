"""VS Code opt-in overlay acceptance contract, runnable without Windows/PySide6.

No real Code.exe or HWND is spawned by these tests; Windows acceptance must
still verify CLI routing, caption, focus, IME and top-level Z order.
"""
import ast
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import vscode_guest_bridge as bridge
import external_preview_route as route


def method(name):
    tree = ast.parse((ROOT/'src/studio_preview_panel.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'StudioPreviewPanel')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {'Path': Path, 'subprocess': SimpleNamespace(Popen=Mock()), 'time': time}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), name, 'exec'), scope)
    return scope[name], scope


class Timer:
    def __init__(self): self.started = False
    def start(self): self.started = True
    def stop(self): self.started = False


class Label:
    def __init__(self): self.text = ''; self.hidden = False
    def setText(self, text): self.text = text
    def setToolTip(self, text): self.tip = text
    def hide(self): self.hidden = True
    def show(self): self.hidden = False


class Signal:
    def __init__(self): self.count = 0
    def emit(self): self.count += 1


class Attached:
    def __init__(self, hwnd, host):
        self.hwnd = hwnd
        self.attached = True
        self.u = SimpleNamespace(IsWindow=lambda h: True)
        self.host = host
        self.events = []
    def resize(self, w, h): self.events.append(('resize', w, h))
    def detach(self, **kw): self.events.append(('detach', kw)); self.attached = False


def panel():
    obj = SimpleNamespace(
        _target=None, _external_pending=None, _external_key=None, _attached=None,
        _external_parked={}, _vscode_profile_dir=None, _vscode_switch_pending=None,
        _vscode_queued=None, _external_timer=Timer(),
        host=SimpleNamespace(winId=lambda: 200, width=lambda: 700, height=lambda: 500),
        title_label=Label(), status_label=Label(),
        content_stack=SimpleNamespace(setCurrentWidget=lambda widget: None),
        popout_requested=Signal(),
        _sync_popout_button=Mock(),
        _park_current=Mock(),
    )
    fn, _ = method('_open_vscode_guest')
    obj._open_vscode_guest = lambda t: fn(obj, t)
    return obj


def target(path='C:/work/hello.py'):
    return route.ExternalPreviewTarget('vscode', path)


def prepare(monkeypatch, tmp_path):
    code = tmp_path / 'Code.exe'
    code.write_bytes(b'fake')
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_LAUNCH_VSCODE_EXE', str(code))
    monkeypatch.setattr(bridge, 'new_profile_root', lambda: tmp_path / 'isolated-session')
    import external_win32_host as host
    monkeypatch.setattr(host, 'snapshot_editor_windows', lambda _: frozenset({10, 20}))
    monkeypatch.setattr('vscode_guest_trace.trace', lambda *a, **k: None)
    return code


def test_default_is_off_and_trial_is_explicit(monkeypatch):
    monkeypatch.delenv('FRB_VSCODE_GUEST_OVERLAY', raising=False)
    assert not bridge.enabled()
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY', '1')
    assert bridge.enabled()
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY', 'true')
    assert not bridge.enabled()


def test_code_suffix_scope_is_explicit_and_preserves_user_editors():
    for filename in ('tool.py', 'hello.js', 'x.MJS', 'index.html', 'style.css', 'a.ts', 'b.tsx', 'parse.go', 'query.sql', 'project.code-workspace'):
        assert bridge.accepts_file(filename), filename
    for filename in ('memo.md', 'note.txt', 'state.ini', 'plan.xlsx', 'start.exe'):
        assert not bridge.accepts_file(filename), filename


def test_route_changes_only_when_opted_in(monkeypatch, tmp_path):
    py = tmp_path / 'step.py'; py.write_text('print(1)', encoding='utf-8')
    monkeypatch.delenv('FRB_VSCODE_GUEST_OVERLAY', raising=False)
    assert route.external_preview_target({'_browse_file': str(py)}) is None
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY', '1')
    assert route.external_preview_target({'_browse_file': str(py)}) == target(str(py))
    assert route.external_preview_target({'_browse_file': str(py), '_launch_virtual_node': {'kind':'file'}}) is None


def test_obsidian_sakura_and_studio_json_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY', '1')
    md = tmp_path / 'A.md'; md.write_text('x', encoding='utf-8')
    txt = tmp_path / 'B.txt'; txt.write_text('x', encoding='utf-8')
    jsn = tmp_path / 'C.json'; jsn.write_text('{}', encoding='utf-8')
    assert route.external_preview_target({'_browse_file': str(md)}).app == 'obsidian'
    assert route.external_preview_target({'_browse_file': str(txt)}, sakura_lookup=lambda:'C:/sakura.exe').app == 'sakura'
    assert route.external_preview_target({'_browse_file': str(jsn)}) is None  # unknown root


def test_executable_override_never_uses_shell_string(monkeypatch, tmp_path):
    exe = tmp_path/'Code.exe'; exe.write_bytes(b'x')
    monkeypatch.setenv('FRB_LAUNCH_VSCODE_EXE', str(exe))
    assert bridge.find_executable() == str(exe)
    monkeypatch.setenv('FRB_LAUNCH_VSCODE_EXE', 'Code.exe & del files')
    assert bridge.find_executable() != 'Code.exe & del files'


def test_persistent_launch_only_profile_across_restarts(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    a, b = bridge.new_profile_root(), bridge.new_profile_root()
    assert a == b == tmp_path/'FRBLaunch'/'VSCodeGuest'/'profile-v1'
    assert 'launch-' not in a.name


def test_cli_commands_share_profile_but_not_existing_desktop_instance():
    profile = Path('C:/FRBLaunch/VSCodeGuest/session')
    a = bridge.command('C:/VS Code/Code.exe', profile, 'C:/hello.py', reuse=False)
    b = bridge.command('C:/VS Code/Code.exe', profile, 'C:/bye.py', reuse=True)
    assert '--new-window' in a and '--reuse-window' not in a
    assert '--reuse-window' in b and '--new-window' not in b
    assert a[0] == b[0] and a[2] == b[2] == str(profile)
    assert isinstance(a, list) and isinstance(b, list)


def test_never_adopt_preexisting_or_ambiguous_window():
    records = [(100, 30, 'hello.py - Visual Studio Code'),
               (200, 31, 'hello.py - Visual Studio Code')]
    assert bridge.new_hwnd_for_file(records, {100}, 'C:/hello.py') == 200
    assert bridge.new_hwnd_for_file(records, {100, 200}, 'C:/hello.py') is None
    assert bridge.new_hwnd_for_file(records, set(), 'C:/hello.py') is None
    assert bridge.new_hwnd_for_file([(200, 31, 'Welcome - Visual Studio Code')], set(), 'C:/hello.py') is None
    assert bridge.new_hwnd_for_file([(200, 31, 'hello.py - Visual Studio Code')], set(), 'C:/bye.py') is None
    assert bridge.caption_matches_file('hello.py - Visual Studio Code', 'C:/hello.py')


def test_first_open_requests_new_window_without_borrowing(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    obj = panel()
    fn, scope = method('_open_vscode_guest')
    popen = Mock()
    scope['subprocess'] = SimpleNamespace(Popen=popen)
    assert fn(obj, target())
    assert obj._external_pending[0] == target()
    assert obj._external_pending[1] == frozenset({10,20})
    assert obj._external_timer.started
    assert obj._external_key is None and obj._attached is None
    assert '--new-window' in popen.call_args.args[0]
    assert obj._vscode_profile_dir == tmp_path/'isolated-session'


def test_rapid_double_click_queues_last_note_no_new_window(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    obj = panel()
    fn, scope = method('_open_vscode_guest')
    popen=Mock(); scope['subprocess'] = SimpleNamespace(Popen=popen)
    assert fn(obj, target('C:/a.py'))
    assert fn(obj, target('C:/b.py'))
    assert fn(obj, target('C:/c.py'))
    assert obj._vscode_queued.path == 'C:/c.py'
    assert popen.call_count == 1


def test_ready_guest_attaches_top_level_overlay_and_completes(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    import external_win32_host as host
    monkeypatch.setattr(host, 'editor_windows', lambda app: [(10,20,'other.py - Visual Studio Code'), (123,30,'hello.py - Visual Studio Code')])
    monkeypatch.setattr('guest_window_overlay.GuestWindowOverlay', Attached)
    obj=panel(); obj._external_pending=(target(), frozenset({10}),None,time.monotonic())
    fn,_=method('_poll_vscode_guest')
    fn(obj)
    assert obj._external_pending is None and not obj._external_timer.started
    assert obj._external_key == target().key
    assert obj._attached.hwnd == 123
    assert ('resize',700,500) in obj._attached.events
    assert obj.status_label.hidden


def test_no_window_within_time_does_not_adopt_or_terminate(monkeypatch, tmp_path):
    prepare(monkeypatch,tmp_path)
    import external_win32_host as host
    monkeypatch.setattr(host,'editor_windows',lambda app: [(10,20,'hello.py - Visual Studio Code')])
    obj=panel();obj._external_pending=(target(),frozenset({10}),None,time.monotonic()-40)
    fn,_=method('_poll_vscode_guest')
    fn(obj)
    assert obj._external_pending is None and obj._attached is None
    assert '確認できません' in obj.status_label.text


def test_switch_reuses_same_profile_and_same_hwnd(monkeypatch,tmp_path):
    prepare(monkeypatch,tmp_path)
    obj=panel(); obj._attached=Attached(123,200)
    obj._external_key=target('C:/a.py').key
    obj._vscode_profile_dir=tmp_path/'isolated-session'
    fn,scope=method('_open_vscode_guest')
    popen=Mock();scope['subprocess']=SimpleNamespace(Popen=popen)
    assert fn(obj,target('C:/b.py'))
    assert '--reuse-window' in popen.call_args.args[0]
    assert '--new-window' not in popen.call_args.args[0]
    assert obj._vscode_switch_pending[0].path=='C:/b.py'
    assert obj._attached.hwnd==123


def test_switch_caption_confirmed_or_timeout_keeps_guest(monkeypatch,tmp_path):
    prepare(monkeypatch,tmp_path)
    import external_win32_host as host
    obj=panel();obj._attached=Attached(123,200)
    obj._external_key=target('C:/a.py').key
    obj._vscode_switch_pending=(target('C:/b.py'),time.monotonic())
    monkeypatch.setattr(host,'editor_window_title',lambda hwnd: 'b.py - Visual Studio Code')
    fn,_=method('_poll_vscode_guest')
    fn(obj)
    assert obj._external_key==target('C:/b.py').key
    assert not obj._external_timer.started
    obj._vscode_switch_pending=(target('C:/c.py'),time.monotonic()-20)
    monkeypatch.setattr(host,'editor_window_title',lambda hwnd: 'b.py - Visual Studio Code')
    fn(obj)
    assert obj._attached.hwnd==123 and obj._external_key==target('C:/b.py').key
    assert '確認できません' in obj.status_label.text


def test_explicit_popout_restores_original_window_and_rotates_profile(monkeypatch,tmp_path):
    prepare(monkeypatch,tmp_path)
    obj=panel();obj._attached=Attached(123,200)
    obj._external_key=target().key;obj._vscode_profile_dir=tmp_path/'session'
    fn,_=method('pop_out_vscode')
    assert fn(obj)
    assert ('detach',{'foreground':True,'show_window':True}) in obj._attached.events if obj._attached else True
    assert obj._attached is None and obj._external_key is None
    assert obj._vscode_profile_dir is None
    assert obj.popout_requested.count==1


def test_static_third_column_switching_and_closing_contract():
    src=(ROOT/'src/studio_preview_panel.py').read_text(encoding='utf-8')
    view=(ROOT/'src/expanded_view.py').read_text(encoding='utf-8')
    assert "if target.app == 'vscode':\n            return self._open_vscode_guest(target)" in src
    assert "self._external_key[0] in ('obsidian', 'vscode')" in src
    assert 'return self.pop_out_vscode()' in src
    assert 'self._poll_vscode_guest()' in src
    assert 'vscode_guest_enabled() if external.app' in view
    assert 'external_preview_target(row, studio_root=studio_root)' in view
    assert 'self._sync_obsidian_ime_overlay' in src  # Shared geometry/Z-order loop
    assert (ROOT/'_run_windows_Try_VSCode_Overlay.bat').is_file()


def test_switch_during_previous_switch_only_queues_last(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    obj=panel()
    obj._attached=Attached(123,200)
    obj._external_key=target('C:/a.py').key
    obj._vscode_profile_dir=tmp_path/'session'
    obj._vscode_switch_pending=(target('C:/b.py'), time.monotonic())
    fn, scope=method('_open_vscode_guest')
    popen=Mock();scope['subprocess']=SimpleNamespace(Popen=popen)
    assert fn(obj,target('C:/c.py'))
    assert obj._vscode_queued==target('C:/c.py')
    popen.assert_not_called()


def test_close_x_parks_editor_without_wmclose(monkeypatch,tmp_path):
    prepare(monkeypatch,tmp_path)
    obj=panel()
    obj._attached=Attached(123,200)
    obj._external_key=target().key
    obj._sakura_switch_from=None
    obj._obsidian_main_probe_token=None
    fn,_=method('_park_external')
    assert fn(obj) is True
    assert obj._external_parked[target().key]==123
    assert obj._external_key is None and obj._attached is None
    assert obj._external_timer.started is False


def test_popout_detaches_window_without_killing_it(monkeypatch,tmp_path):
    prepare(monkeypatch,tmp_path)
    obj=panel()
    attached=Attached(123,200)
    obj._attached=attached
    obj._external_key=target().key
    obj._vscode_profile_dir=tmp_path/'session'
    fn,_=method('pop_out_vscode')
    assert fn(obj)
    assert attached.events[-1] == ('detach', {'foreground':True,'show_window':True})
    assert obj.popout_requested.count == 1
    assert obj._vscode_profile_dir is None


def test_vscode_close_detected_and_third_column_hidden():
    obj=panel()
    obj._attached=Attached(123,200)
    obj._external_key=target().key
    obj._attached.u.IsWindow=lambda hwnd: False
    obj._vscode_profile_dir=Path('C:/isolated')
    obj.isHidden=lambda:False
    fn,_=method('_check_embedded_editor_health')
    fn(obj)
    assert obj._external_key is None and obj._attached is None
    assert obj.popout_requested.count==1
    assert obj._vscode_profile_dir is None


def test_vscode_healthy_guest_does_not_close_third_column():
    obj=panel()
    obj._attached=Attached(123,200)
    obj._external_key=target().key
    obj.isHidden=lambda:False
    fn,_=method('_check_embedded_editor_health')
    fn(obj)
    assert obj.popout_requested.count==0
    assert obj._external_key == target().key


def test_overlay_adapter_is_non_parenting():
    from guest_window_overlay import GuestWindowOverlay
    from obsidian_ime_overlay import ObsidianImeOverlay
    assert issubclass(GuestWindowOverlay, ObsidianImeOverlay)
    code=(ROOT/'src/obsidian_ime_overlay.py').read_text(encoding='utf-8')
    assert 'SetParent(' not in code


def test_nonmanaged_json_routes_to_vscode_but_managed_json_stays_studio(monkeypatch,tmp_path):
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY','1')
    import file_index
    f=tmp_path/'app.json';f.write_text('{}',encoding='utf-8')
    monkeypatch.setattr(file_index,'studio_managed_json',lambda path,root: False)
    assert route.external_preview_target({'_browse_file':str(f)},studio_root=tmp_path).app=='vscode'
    monkeypatch.setattr(file_index,'studio_managed_json',lambda path,root: True)
    assert route.external_preview_target({'_browse_file':str(f)},studio_root=tmp_path) is None
