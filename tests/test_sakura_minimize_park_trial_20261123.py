"""A/B Sakura minimize parking is opt-in and keeps known HWNDs alive.

These are fake-Win32 lifecycle tests, not actual DWM pixel tests.
"""
import os
from test_sakura_native_popout_restore_20261119 import RecorderWin32, Fn
from guest_window_overlay import SakuraGuestOverlay


class FakeMinimizable(RecorderWin32):
    def __init__(self):
        super().__init__()
        self.iconic = False
        self.IsIconic = Fn(lambda hwnd: self.iconic)
        self.IsWindowVisible = Fn(lambda hwnd: self.visible)

    def ShowWindow(self, hwnd, style):
        self.calls.append(('show', style))
        if style == 7:  # SW_SHOWMINNOACTIVE
            self.iconic = True
        elif style in (4, 9):  # SW_SHOWNOACTIVATE or SW_RESTORE
            self.iconic = False
            self.visible = True
        elif style == 0:
            self.visible = False
        return True


def test_trial_mode_minimizes_without_hide_or_closing(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_PARK_MODE', 'minimize')
    import sakura_window_trace
    events = []
    monkeypatch.setattr(sakura_window_trace, 'trace',
                        lambda event, **kw: events.append((event, kw)))
    api = FakeMinimizable()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()
    guest.detach(foreground=False, show_window=False)
    assert api.iconic
    assert not guest.attached
    assert ('show', 7) in api.calls
    assert ('show', 0) not in api.calls
    assert not any(c[0] == 'place' and c[-1] & 0x80 for c in api.calls)
    assert not any(c[0] in ('close', 'kill', 'parent') for c in api.calls)
    logs = [v for e, v in events if e == 'PARKED_MINIMIZE_TRIAL_RESULT']
    assert len(logs) == 1 and logs[0]['actual_minimized'] is True


def test_minimized_guest_is_restored_before_capturing_rect(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_PARK_MODE', 'minimize')
    api = FakeMinimizable()
    first = SakuraGuestOverlay(100, 200, user32=api)
    first.detach(foreground=False, show_window=False)
    assert api.iconic
    api.calls.clear()
    second = SakuraGuestOverlay(100, 200, user32=api)
    assert second.attached and not api.iconic
    assert ('show', 4) in api.calls  # restore before overlay construction
    second.detach(foreground=False, show_window=True)
    assert not api.iconic
    assert ('show', 4) in api.calls


def test_default_remains_existing_atomic_hide(monkeypatch):
    monkeypatch.delenv('FRB_SAKURA_PARK_MODE', raising=False)
    api = FakeMinimizable()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()
    guest.detach(foreground=False, show_window=False)
    assert any(c[0] == 'place' and c[-1] & 0x80 for c in api.calls)
    assert ('show', 7) not in api.calls
    assert not api.iconic


def test_minimize_failure_retains_attached_ownership(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_PARK_MODE', 'minimize')
    class FailMinimize(FakeMinimizable):
        def ShowWindow(self, hwnd, style):
            if style == 7:
                self.calls.append(('show', style))
                return False
            return super().ShowWindow(hwnd, style)
    api = FailMinimize()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    try:
        guest.detach(foreground=False, show_window=False)
        assert False, 'expected parking failure'
    except OSError:
        pass
    assert guest.attached and not api.iconic
