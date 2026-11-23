"""Sakura: during intentional parking an overlay timer must not re-show a hidden editor.

Win32 fake models nested notification during atomic SetWindowPos(SWP_HIDEWINDOW).
Windows/DWM pixel behavior remains an independent manual acceptance test.
"""
from guest_window_overlay import SakuraGuestOverlay
from test_sakura_overlay_transient_recovery_20261122 import VisibilityWin32, Fn
from studio_win32_host import SW_HIDE, SWP_SHOWWINDOW


def test_sync_reentry_cannot_undo_intentional_hidden_park():
    api = VisibilityWin32()
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    unguarded_observed = []
    underlying_place = api.SetWindowPos
    def place_and_deliver_nested_tick(hwnd, after, x, y, w, h, flags):
        placed = underlying_place(hwnd, after, x, y, w, h, flags)
        if flags & 0x0080:  # SWP_HIDEWINDOW
            overlay.sync(panel_visible=True)
            unguarded_observed.append(api.visible)
        return placed
    api.SetWindowPos = Fn(place_and_deliver_nested_tick)
    api.calls.clear()
    overlay.detach(foreground=False, show_window=False)
    assert unguarded_observed == [False], 'sync must not re-show while detaching'
    assert not api.visible, 'hidden park must end truly hidden'
    assert not overlay.attached
    assert not any(c[0] == 'place' and c[-1] & SWP_SHOWWINDOW for c in api.calls)
    assert ('show', SW_HIDE) not in api.calls


def test_sync_heartbeat_records_observed_native_geometry(monkeypatch):
    import sakura_window_trace
    api = VisibilityWin32()
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    recorded = []
    monkeypatch.setattr(sakura_window_trace, 'trace',
                        lambda event, **fields: recorded.append((event, fields)))
    overlay._trace_sakura_sync('SYNC_HEARTBEAT', force=True)
    event, fields = recorded[-1]
    assert event == 'SYNC_HEARTBEAT'
    assert fields['native_guest_rect'] is not None
    assert fields['planned_host_rect'] is not None


def test_parked_sakura_visibility_probe_does_not_move_or_show_windows():
    import ast
    from pathlib import Path
    from types import SimpleNamespace as NS
    import time
    path = Path(__file__).resolve().parents[1] / 'src' / 'studio_preview_panel.py'
    module = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef)
               and n.name == 'StudioPreviewPanel')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_trace_sakura_parked_state')
    namespace = {'time': time}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 '<parked-observation>', 'exec'), namespace)
    calls = []
    class ReadOnlyApi:
        def IsWindow(self, hwnd): calls.append(('IsWindow', hwnd)); return True
        def IsWindowVisible(self, hwnd): calls.append(('IsWindowVisible', hwnd)); return False
        def IsIconic(self, hwnd): calls.append(('IsIconic', hwnd)); return False
    events = []
    parked_key = ('sakura', 'c:/demo/001.txt')
    panel = NS(_external_key=('sakura', 'c:/demo/002.txt'),
               _external_parked={parked_key: 222}, _auto_ejected_keys=set(),
               _sakura_trace=lambda event, **fields: events.append((event, fields)))
    namespace['_trace_sakura_parked_state'](panel, NS(hwnd=111, u=ReadOnlyApi()))
    assert events[0][0] == 'PARKED_SAKURA_STATE'
    assert events[0][1]['parked'] == [dict(hwnd=222, alive=True,
                                           auto_ejected_marker=False,
                                           actual_visible=False, minimized=False)]
    assert {name for name, hwnd in calls} == {
        'IsWindow', 'IsWindowVisible', 'IsIconic'}
