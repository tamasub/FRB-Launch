"""2026-11-22 Sakura GDI: Launch moves may not hide its third-column guest.

Fake Win32 only; a manual Windows move/click repro still needs verification.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from guest_window_overlay import SakuraGuestOverlay
from studio_win32_host import SW_HIDE, SW_RESTORE, SWP_SHOWWINDOW
from test_sakura_native_popout_restore_20261119 import RecorderWin32, Fn


class VisibilityWin32(RecorderWin32):
    def __init__(self):
        super().__init__()
        self.root_shown = True
        self.root_iconic = False
        self.guest_iconic = False
        self.IsWindowVisible = Fn(lambda hwnd: self.root_shown if hwnd == 999 else self.visible)
        self.IsIconic = Fn(lambda hwnd: self.root_iconic if hwnd == 999 else self.guest_iconic)
        self.ShowWindow = Fn(self.show)
        self.fail_geometry = False

    def get_client_rect(self, hwnd, out):
        if self.fail_geometry:
            return False
        return super().get_client_rect(hwnd, out)

    def SetWindowPos(self, hwnd, after, x, y, w, h, flags):
        done = super().SetWindowPos(hwnd, after, x, y, w, h, flags)
        if done and flags & SWP_SHOWWINDOW:
            self.visible = True
        if done and flags & 0x0080:
            self.visible = False
        return done

    def show(self, hwnd, command):
        self.calls.append(('show', command))
        self.visible = command != SW_HIDE
        if command == SW_RESTORE:
            self.guest_iconic = False
        return True


def test_qt_panel_visibility_blip_during_drag_does_not_hide_sakura():
    api = VisibilityWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()
    guest.sync(panel_visible=False)
    assert guest.attached and guest._visible
    assert api.visible
    assert ('show', SW_HIDE) not in api.calls


def test_temporary_native_host_geometry_failure_does_not_hide_sakura():
    api = VisibilityWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.fail_geometry = True
    api.calls.clear()
    guest.sync(panel_visible=True)
    assert guest.attached and guest._visible and api.visible
    assert ('show', SW_HIDE) not in api.calls
    api.fail_geometry = False
    api.host_rect = (400, 150, 610, 400)
    guest.sync(panel_visible=True)
    assert guest._last_rect == (400, 150, 610, 400)


def test_real_launch_minimize_still_hides_and_restore_reshows_sakura():
    api = VisibilityWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.root_iconic = True
    api.calls.clear()
    guest.sync(panel_visible=False)
    assert ('show', SW_HIDE) in api.calls
    assert not api.visible
    api.root_iconic = False
    guest.sync(panel_visible=True)
    assert api.visible and guest._visible


def test_unexpected_guest_hide_is_recovered_without_new_process():
    api = VisibilityWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.visible = False  # external Windows or Qt hide, not a user popup action
    api.calls.clear()
    guest.sync(panel_visible=True)
    assert guest.attached and api.visible
    assert any(c[0] == 'place' and c[-1] & SWP_SHOWWINDOW for c in api.calls)


def test_unexpected_guest_iconify_is_restored_without_process_restart():
    api = VisibilityWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.guest_iconic = True
    api.calls.clear()
    guest.sync(panel_visible=True)
    assert ('show', SW_RESTORE) in api.calls
    assert not api.guest_iconic and guest.attached and guest._visible


def test_sakura_trace_can_be_disabled_via_state_ini(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    state_dir = tmp_path / 'FRBLaunch'
    state_dir.mkdir()
    from sakura_window_trace import trace, enabled
    (state_dir / 'state.ini').write_text('[General]\nsakura_trace_enabled=false\n', encoding='utf-8')
    assert not enabled()
    trace('SHOULD_NOT_WRITE', hwnd=10)
    assert not (state_dir / 'sakura_window_trace.log').exists()
    (state_dir / 'state.ini').write_text('[General]\nsakura_trace_enabled=true\n', encoding='utf-8')
    assert enabled()
    trace('NOW_ON', hwnd=10)
    event = json.loads((state_dir / 'sakura_window_trace.log').read_text(encoding='utf-8').strip())
    assert event['event'] == 'NOW_ON'


def method(name):
    src = Path(__file__).resolve().parents[1] / 'src' / 'studio_preview_panel.py'
    tree = ast.parse(src.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'StudioPreviewPanel')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(src), 'exec'), ns)
    return ns[name]


def test_explicit_popout_keeps_verified_hwnd_and_identity():
    calls = []
    class Overlay:
        hwnd=1234
        attached=True
        is_ime_overlay=True
        def detach(self, **kwargs):
            calls.append(('detach', kwargs))
            self.attached=False
    key = ('sakura', 'c:/notes/a.txt')
    owner = NS(_attached=Overlay(), _external_key=key,
               _external_pending=None, _sakura_guest_switch=None,
               _external_parked={}, _sakura_parked_pids={}, _auto_ejected_keys=set(),
               _remember_sakura_parked_pid=lambda hwnd: calls.append(('remember', hwnd)),
               _sync_popout_button=lambda: None,
               popout_requested=NS(emit=lambda: calls.append(('emit',))),
               _sakura_trace=lambda *a, **k: None)
    assert method('pop_out_sakura_guest')(owner)
    assert owner._external_parked == {key: 1234}
    assert key in owner._auto_ejected_keys
    assert ('remember', 1234) in calls
    assert ('emit',) in calls


def test_parked_identity_rejects_hwnd_pid_reuse(monkeypatch):
    from external_win32_host import editor_window_pid
    import external_win32_host
    monkeypatch.setattr(external_win32_host, 'editor_window_pid', lambda hwnd: 222)
    owner = NS(_sakura_parked_pids={111: 123}, _sakura_trace=lambda *a, **kw: None)
    assert not method('_sakura_parked_pid_matches')(owner, 111)
    assert method('_sakura_parked_pid_matches')(owner, 222)


def test_list_single_click_only_selects_file_not_preview():
    """Use the real Files List click handler; only activate_row opens a file."""
    source = Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'ExpandedLauncherView')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == 'choose_middle')
    fake_qt = NS(KeyboardModifier=NS(ControlModifier=1, ShiftModifier=2))
    ns = {'QApplication': NS(keyboardModifiers=lambda: 0), 'Qt': fake_qt}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(source), 'exec'), ns)
    events = []
    owner = NS(row_data=lambda item: {'item_kind': 'file', '_browse_file': 'C:/demo.txt'},
               preview_bookmark_from_list=lambda row: events.append('preview'))
    ns['choose_middle'](owner, object(), 0)
    assert not events
