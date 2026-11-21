"""VS Code third-column re-seat fallback; Qt/Windows-independent contract tests.

The fallback must not borrow unrelated Code windows and must not end in a
blank third column when the stored HWND/PID or normal restore is unavailable.
"""
from types import SimpleNamespace
from unittest.mock import Mock

from test_vscode_guest_overlay_20261119 import (Attached, method, panel, prepare,
                                                  target)


def setup_parked(monkeypatch, tmp_path, *, windows=None):
    prepare(monkeypatch, tmp_path)
    import external_win32_host as win
    import vscode_guest_bridge as bridge
    import guest_window_overlay as overlay
    key = target().key
    obj = panel()
    obj._external_parked = {key: 123}
    obj._vscode_window_pids = {123: 99}
    obj._auto_ejected_keys = {key}
    obj._vscode_profile_dir = tmp_path / 'isolated-session'
    monkeypatch.setattr(win, 'editor_windows', lambda app, **kwargs: (
        [(123, 99, 'hello.py - Visual Studio Code')]
        if windows is None else windows))
    monkeypatch.setattr(bridge, 'show_previous_window', lambda hwnd: True)
    monkeypatch.setattr(overlay, 'GuestWindowOverlay', Attached)
    fn, scope = method('_open_vscode_guest')
    popen = Mock()
    scope['subprocess'] = SimpleNamespace(Popen=popen)
    return obj, fn, popen, key


def assert_fresh_started(obj, popen, key):
    assert popen.call_count == 1
    assert '--new-window' in popen.call_args.args[0]
    assert '--reuse-window' not in popen.call_args.args[0]
    assert obj._external_pending[0] == target()
    assert obj._external_timer.started
    assert obj._external_key is None and obj._attached is None
    assert key not in obj._external_parked
    assert key not in obj._auto_ejected_keys
    assert 123 not in obj._vscode_window_pids


def test_verified_same_hwnd_pid_redocks_without_opening_new(monkeypatch, tmp_path):
    obj, fn, popen, key = setup_parked(monkeypatch, tmp_path)
    assert fn(obj, target())
    assert obj._attached.hwnd == 123
    assert obj._external_key == key
    assert popen.call_count == 0
    assert obj._external_pending is None
    assert key not in obj._external_parked


def test_stale_pid_falls_back_to_new_window(monkeypatch, tmp_path):
    obj, fn, popen, key = setup_parked(
        monkeypatch, tmp_path, windows=[(123, 777, 'hello.py - Visual Studio Code')])
    assert fn(obj, target())
    assert_fresh_started(obj, popen, key)


def test_stale_hwnd_falls_back_to_new_window(monkeypatch, tmp_path):
    obj, fn, popen, key = setup_parked(
        monkeypatch, tmp_path, windows=[(555, 99, 'hello.py - Visual Studio Code')])
    assert fn(obj, target())
    assert_fresh_started(obj, popen, key)


def test_existing_window_wont_restore_still_opens_new(monkeypatch, tmp_path):
    import vscode_guest_bridge as bridge
    obj, fn, popen, key = setup_parked(monkeypatch, tmp_path)
    monkeypatch.setattr(bridge, 'show_previous_window', lambda hwnd: False)
    assert fn(obj, target())
    assert_fresh_started(obj, popen, key)


def test_overlay_resize_fails_old_window_restored_then_new(monkeypatch, tmp_path):
    import guest_window_overlay as overlay
    obj, fn, popen, key = setup_parked(monkeypatch, tmp_path)
    created = []
    class FaultyOverlay(Attached):
        def __init__(self, hwnd, host):
            super().__init__(hwnd, host)
            created.append(self)
        def resize(self, w, h):
            raise RuntimeError('native host resized')
    monkeypatch.setattr(overlay, 'GuestWindowOverlay', FaultyOverlay)
    assert fn(obj, target())
    assert created[0].events == [('detach', {'foreground': False, 'show_window': True})]
    assert not created[0].attached
    assert_fresh_started(obj, popen, key)


def test_unsafe_to_detach_blocks_new_to_protect_editor(monkeypatch, tmp_path):
    import guest_window_overlay as overlay
    obj, fn, popen, key = setup_parked(monkeypatch, tmp_path)
    class CannotRestore(Attached):
        def resize(self, w, h):
            raise OSError('resize failed')
        def detach(self, **kwargs):
            raise OSError('native detach failed')
    monkeypatch.setattr(overlay, 'GuestWindowOverlay', CannotRestore)
    assert fn(obj, target()) is False
    assert obj._attached.hwnd == 123
    assert obj._attached.attached
    assert obj._external_key == key
    assert popen.call_count == 0
    assert obj._external_pending is None


def test_auto_switch_ejects_to_desktop_and_reselect_redocks_same_window(
        monkeypatch, tmp_path):
    """The two user actions form one safe roundtrip without an extra Code.exe."""
    import external_win32_host as win
    obj, fn, popen, key = setup_parked(monkeypatch, tmp_path)
    monkeypatch.setattr(win, 'editor_window_pid', lambda hwnd: 99)
    old = Attached(123, 200)
    obj._external_key = key
    obj._attached = old
    obj._external_parked.clear()
    obj._auto_ejected_keys.clear()
    obj._obsidian_cli_busy = None
    obj._sakura_guest_switch = None
    obj._sakura_switch_from = None
    eject, _ = method('auto_release_external_for_switch')
    park, _ = method('_park_external')
    obj._park_external = lambda **kw: park(obj, **kw)
    assert eject(obj) is True  # another app is about to take the third column
    assert not old.attached
    assert ('detach', {'foreground': False, 'show_window': True}) in old.events
    assert obj._attached is None and obj._external_key is None
    assert obj._external_parked[key] == 123
    assert key in obj._auto_ejected_keys
    assert obj._vscode_window_pids[123] == 99
    # The user double-clicks the same JSON again in Exp/List.
    assert fn(obj, target()) is True
    assert obj._attached.hwnd == 123 and obj._attached.attached
    assert popen.call_count == 0
    assert key not in obj._external_parked
    assert key not in obj._auto_ejected_keys


def test_auto_switch_never_kills_or_hides_a_live_vscode_window(monkeypatch, tmp_path):
    import external_win32_host as win
    obj, _, _, key = setup_parked(monkeypatch, tmp_path)
    monkeypatch.setattr(win, 'editor_window_pid', lambda hwnd: 99)
    obj._attached = Attached(123, 200)
    obj._external_key = key
    obj._external_parked.clear()
    obj._obsidian_cli_busy = None
    obj._sakura_guest_switch = None
    obj._sakura_switch_from = None
    park, _ = method('_park_external')
    assert park(obj, desktop=True)
    assert not hasattr(obj, '_process') or obj._process is None
    assert obj._attached is None
    assert obj._external_parked[key] == 123


def test_hwnd_enumeration_failure_falls_back_to_fresh(monkeypatch, tmp_path):
    import external_win32_host as win
    obj, fn, popen, key = setup_parked(monkeypatch, tmp_path)
    def unavailable(*args, **kwargs):
        raise OSError('Win32 enumeration unavailable')
    monkeypatch.setattr(win, 'editor_windows', unavailable)
    assert fn(obj, target())
    assert_fresh_started(obj, popen, key)
