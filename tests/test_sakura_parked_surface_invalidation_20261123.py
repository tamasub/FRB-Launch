"""Hidden Sakura GDI surface invalidation after a file handoff.

Win32 fakes verify calls, not the final DWM-composited pixels. Visual
acceptance remains necessary on a real Windows desktop.
"""
from test_sakura_native_popout_restore_20261119 import RecorderWin32
from guest_window_overlay import SakuraGuestOverlay
from studio_win32_host import RDW_INVALIDATE, RDW_ALLCHILDREN

SWP_HIDEWINDOW = 0x0080
SWP_NOCOPYBITS = 0x0100
SWP_SHOWWINDOW = 0x0040


def test_hidden_retired_hwnd_drops_client_pixels_and_redraws_launch(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_PARK_MODE', 'hide')
    api = RecorderWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()
    guest.detach(foreground=False, show_window=False)
    places = [v for v in api.calls if v[0] == 'place' and v[1] == 100]
    assert len(places) == 1
    assert places[0][-1] & (SWP_HIDEWINDOW | SWP_NOCOPYBITS) == (SWP_HIDEWINDOW | SWP_NOCOPYBITS)
    assert not places[0][-1] & SWP_SHOWWINDOW
    assert any(c[0] == 'redraw' and c[1] == 999
               and c[2] & RDW_INVALIDATE and c[2] & RDW_ALLCHILDREN
               for c in api.calls)
    assert not any(c[0] == 'redraw' and c[1] == 100 for c in api.calls)
    assert not any(c[0] == 'foreground' for c in api.calls)
    assert guest.attached is False
    assert api.visible is False


def test_explicit_popout_remains_visible_with_no_extra_root_redraw():
    api = RecorderWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()
    guest.detach(foreground=False, show_window=True)
    assert api.visible is True
    assert ('show', 4) in api.calls
    assert not any(c[0] == 'redraw' and c[1] == 999 for c in api.calls)
    assert not any(c[0] == 'place' and c[1] == 100
                   and c[-1] & (SWP_HIDEWINDOW | SWP_NOCOPYBITS)
                   for c in api.calls)
