"""Atomic Win32 hide+position contract for a retired Sakura overlay.

Fake API checks one native operation, fallback behavior and ownership safety.
DWM residual pixels must be checked on the user's real Windows desktop.
"""
import pytest
from guest_window_overlay import SakuraGuestOverlay
from test_sakura_native_popout_restore_20261119 import RecorderWin32, Fn

SW_HIDE = 0
SWP_HIDEWINDOW = 0x0080
SWP_NOCOPYBITS = 0x0100
SWP_SHOWWINDOW = 0x0040


@pytest.fixture(autouse=True)
def test_legacy_atomic_hide_only(monkeypatch):
    """These tests specifically exercise the explicit hide rollback path."""
    monkeypatch.setenv('FRB_SAKURA_PARK_MODE', 'hide')


def test_park_hides_in_one_native_position_transaction(monkeypatch):
    import sakura_window_trace
    events = []
    monkeypatch.setattr(sakura_window_trace, 'trace',
                        lambda event, **kw: events.append((event, kw)))
    api = RecorderWin32()
    api.IsWindowVisible = Fn(lambda hwnd: api.visible)
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()

    guest.detach(foreground=False, show_window=False)

    position_calls = [x for x in api.calls if x[0] == 'place' and x[1] == 100]
    assert len(position_calls) == 1
    assert position_calls[0][3:7] == (100, 100, 900, 700)
    assert position_calls[0][-1] & (SWP_HIDEWINDOW | SWP_NOCOPYBITS) == (SWP_HIDEWINDOW | SWP_NOCOPYBITS)
    assert not position_calls[0][-1] & SWP_SHOWWINDOW
    assert ('show', SW_HIDE) not in api.calls
    assert api.visible is False
    assert guest.attached is False
    result = [fields for event, fields in events if event == 'PARKED_ATOMIC_HIDE_RESULT']
    assert len(result) == 1
    assert result[0]['hide_fallback_used'] is False
    assert result[0]['actual_hidden'] is True


def test_park_falls_back_to_showwindow_only_if_native_hide_was_ignored(monkeypatch):
    import sakura_window_trace
    events = []
    monkeypatch.setattr(sakura_window_trace, 'trace',
                        lambda event, **kw: events.append((event, kw)))

    class IgnoreAtomicHide(RecorderWin32):
        def SetWindowPos(self, hwnd, after, x, y, w, h, flags):
            result = super().SetWindowPos(hwnd, after, x, y, w, h, flags)
            if flags & SWP_HIDEWINDOW:
                self.visible = True  # native app vetoed hide
            return result
    api = IgnoreAtomicHide()
    api.IsWindowVisible = Fn(lambda hwnd: api.visible)
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()

    guest.detach(foreground=False, show_window=False)

    assert ('show', SW_HIDE) in api.calls
    assert not api.visible
    assert guest.attached is False
    result = [fields for event, fields in events if event == 'PARKED_ATOMIC_HIDE_RESULT']
    assert result[-1]['hide_fallback_used'] is True
    assert result[-1]['actual_hidden'] is True


def test_still_visible_guest_is_not_registered_as_detached():
    class CannotHide(RecorderWin32):
        def SetWindowPos(self, hwnd, after, x, y, w, h, flags):
            result = super().SetWindowPos(hwnd, after, x, y, w, h, flags)
            if flags & SWP_HIDEWINDOW:
                self.visible = True
            return result
        def ShowWindow(self, hwnd, command):
            self.calls.append(('show', command))
            return True  # intentionally ignored
    api = CannotHide()
    api.IsWindowVisible = Fn(lambda hwnd: api.visible)
    guest = SakuraGuestOverlay(100, 200, user32=api)

    try:
        guest.detach(foreground=False, show_window=False)
        assert False, 'hide must fail instead of recording this window as parked'
    except OSError:
        pass
    assert guest.attached is True
    assert api.visible is True


def test_failed_native_transaction_cannot_retire_live_hwnd():
    api = RecorderWin32()
    api.fail_pos = False
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.fail_pos = True
    api.calls.clear()
    try:
        guest.detach(foreground=False, show_window=False)
        assert False, 'expect exception'
    except OSError:
        pass
    assert guest.attached
    assert api.visible  # no preliminary ShowWindow(SW_HIDE)
    assert ('show', SW_HIDE) not in api.calls
