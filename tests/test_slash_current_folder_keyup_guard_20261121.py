"""Regression: deep Qt.Tool close may observe Enter KeyUp as newer Win32 input.

These portable tests use simulated native snapshots. Windows GUI smoke remains
necessary to verify actual GetAsyncKeyState timing on a 5/6-level cascade.
"""
from types import SimpleNamespace

import pytest
import windows


def _snapshot(*, enter=True, x=50, y=100, keys=(), mouse=False):
    return {'enter_down': enter, 'pointer': (x, y),
            'other_down': frozenset(keys), 'mouse_activity': mouse}


def _harness(monkeypatch):
    state = {'tick': 10000, 'front': 888, 'time': 100.0,
             'snapshot': _snapshot(enter=True)}
    calls = []
    monkeypatch.setattr(windows, 'IS_WINDOWS', True)
    monkeypatch.setattr(windows, 'user', SimpleNamespace(IsWindow=lambda hwnd: hwnd in (111, 222)), raising=False)
    monkeypatch.setattr(windows, 'foreground', lambda: state['front'])
    monkeypatch.setattr(windows, 'last_user_input_tick', lambda: state['tick'])
    monkeypatch.setattr(windows.time, 'monotonic', lambda: state['time'])
    monkeypatch.setattr(windows, '_menu_handoff_input_snapshot', lambda: state['snapshot'])
    monkeypatch.setattr(windows, 'raise_normal_window', lambda hwnd: calls.append(('raise', hwnd)) or True)
    monkeypatch.setattr(windows, 'activate_keyboard_window',
                        lambda hwnd, expected_foreground: calls.append(('activate', hwnd)) or True)
    state['front'] = 111
    ticket = windows.capture_menu_enter_handoff(111, 222)
    assert ticket is not None
    state['front'] = 888  # Chrome returns to foreground when native menus hide.
    return state, calls, ticket


def test_deep_menu_accepts_only_enter_keyup_transition(monkeypatch):
    state, calls, ticket = _harness(monkeypatch)
    state.update(tick=10094, time=100.105, snapshot=_snapshot(enter=False))
    assert windows.finish_menu_enter_handoff(222, ticket) is True
    assert ticket[3]['accepted_release_tick'] == 10094
    assert calls == [('raise', 222), ('activate', 222)]
    # A second guarded retry may see the same KeyUp tick, without revocation.
    calls.clear()
    assert windows.finish_menu_enter_handoff(222, ticket) is True
    assert calls == [('raise', 222), ('activate', 222)]
    # But the very next input (e.g. clicking Chrome) invalidates the ticket.
    calls.clear()
    state.update(tick=10123, time=100.13)
    assert windows.finish_menu_enter_handoff(222, ticket) is False
    assert calls == []


def test_chrome_click_during_menu_close_cannot_be_mistaken_for_keyup(monkeypatch):
    for changed in (_snapshot(enter=False, x=55),
                    _snapshot(enter=False, mouse=True),
                    _snapshot(enter=True),
                    _snapshot(enter=False, keys=(0x41,))):
        state, calls, ticket = _harness(monkeypatch)
        state.update(tick=10094, time=100.105, snapshot=changed)
        assert windows.finish_menu_enter_handoff(222, ticket) is False
        assert calls == []


def test_late_or_unverified_keyup_stays_rejected(monkeypatch):
    state, calls, ticket = _harness(monkeypatch)
    state.update(tick=10260, time=100.27, snapshot=_snapshot(enter=False))
    assert windows.finish_menu_enter_handoff(222, ticket) is False  # >250 ms
    state.update(tick=10094, time=100.45)
    assert windows.finish_menu_enter_handoff(222, ticket) is False  # too old
    ticket[3]['initial'] = None
    state['time'] = 100.10
    assert windows.finish_menu_enter_handoff(222, ticket) is False
    assert calls == []


def test_legacy_three_field_ticket_retains_strict_guard(monkeypatch):
    state, calls, ticket = _harness(monkeypatch)
    state.update(tick=10094, time=100.10, snapshot=_snapshot(enter=False))
    assert windows.finish_menu_enter_handoff(222, ticket[:3]) is False
    assert calls == []


def test_original_keypress_without_new_input_still_succeeds(monkeypatch):
    state, calls, ticket = _harness(monkeypatch)
    state.update(time=100.02)
    assert windows.finish_menu_enter_handoff(222, ticket) is True
    assert ticket[3]['accepted_release_tick'] is None


@pytest.mark.parametrize('depth,close_ms,key_up', [
    (2, 34, False),  # shallow: still seeing the original KeyDown tick
    (5, 93, True),   # deep: Qt.Tool closes after Enter KeyUp
    (6, 105, True),
])
def test_menu_depth_does_not_change_handoff_policy(monkeypatch, depth, close_ms, key_up):
    state, calls, ticket = _harness(monkeypatch)
    state['time'] = 100.0 + close_ms / 1000
    if key_up:
        state.update(tick=10000 + close_ms, snapshot=_snapshot(enter=False))
    assert windows.finish_menu_enter_handoff(222, ticket) is True, depth
    assert calls == [('raise', 222), ('activate', 222)]
