"""The diagnostics must see a visible Sakura underneath Launch without moving it.

This is a Win32 API fake, not a verification of real Windows pixels.
"""
from guest_window_overlay import SakuraGuestOverlay
from test_sakura_overlay_transient_recovery_20261122 import VisibilityWin32, Fn


class OccludedWin32(VisibilityWin32):
    def __init__(self):
        super().__init__()
        # The main Launch root (999) is higher than Sakura (100).
        self.GetWindow = Fn(lambda hwnd, mode: (999 if hwnd == 100 else 0)
                            if mode == 3 else 0)
        self.WindowFromPoint = Fn(lambda point: 999)
        self.GetAncestor = lambda hwnd, which: 999 if hwnd in (200, 999) else hwnd


def test_probe_detects_sakura_behind_launch_without_touching_zorder():
    api = OccludedWin32()
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()
    diagnostic = overlay._sakura_native_stacking()
    assert diagnostic['native_root_hwnd'] == 999
    assert diagnostic['native_guest_immediately_above_root'] is False
    assert diagnostic['native_guest_above_root'] is False
    assert diagnostic['native_root_above_guest'] is True
    assert diagnostic['native_launch_is_hit_root'] is True
    assert diagnostic['native_guest_is_hit_root'] is False
    assert api.calls == [], 'diagnostic must be read-only'


def test_heartbeat_includes_zorder_diagnostic(monkeypatch):
    import sakura_window_trace
    api = OccludedWin32()
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    events = []
    monkeypatch.setattr(sakura_window_trace, 'trace',
                        lambda event, **data: events.append((event, data)))
    overlay._trace_sakura_sync('SYNC_HEARTBEAT', force=True)
    assert events[-1][0] == 'SYNC_HEARTBEAT'
    assert events[-1][1]['native_root_above_guest'] is True
    assert events[-1][1]['native_hit_root_hwnd'] == 999


def test_diagnostic_without_optional_hit_test_remains_safe():
    api = VisibilityWin32()  # existing API fake has no WindowFromPoint
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    assert overlay._sakura_native_stacking()['native_root_hwnd'] == 999
