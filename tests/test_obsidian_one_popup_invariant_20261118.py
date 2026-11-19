"""One-window-per-Launch-Obsidian-session regression, without PySide6/Win32.

Execute the real class method bodies against state-machine doubles. Windows
Electron rendering, vault/CLI readiness and SetParent require device testing.
"""
import ast
import os
import subprocess
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from external_preview_route import ExternalPreviewTarget

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src' / 'studio_preview_panel.py'
TREE = ast.parse(SRC.read_text(encoding='utf-8'))
PANEL = next(node for node in TREE.body if isinstance(node, ast.ClassDef)
             and node.name == 'StudioPreviewPanel')


def method(name):
    func = next(node for node in PANEL.body if isinstance(node, ast.FunctionDef)
                and node.name == name)
    scope = {'Path': Path, 'time': time, 'os': os, 'subprocess': subprocess,
             'uuid': uuid}
    exec(compile(ast.Module(body=[func], type_ignores=[]), f'<{name}>', 'exec'), scope)
    return scope[name]


class Status:
    def __init__(self): self.text = ''; self.visible = False
    def setText(self, text): self.text = text
    def show(self): self.visible = True
    def hide(self): self.visible = False


class Attached:
    def __init__(self, hwnd): self.hwnd = hwnd; self.attached = True; self.sizes = []
    def resize(self, w, h): self.sizes.append((w, h))


class Timer:
    def __init__(self): self.running = False
    def start(self): self.running = True
    def stop(self): self.running = False


@pytest.fixture(autouse=True)
def cli_registered_for_legacy_same_vault_tests(monkeypatch):
    # These original one-popup tests exercise only notes A/B/C inside ONE vault.
    # Multi-vault transitions are covered by test_obsidian_vault_switch_20261118.
    import obsidian_dock_bridge as bridge
    monkeypatch.setattr(bridge, 'registered_note',
                        lambda path: ('vault-id', Path(path).name))
    monkeypatch.setattr(bridge, 'find_cli', lambda: 'Obsidian.com')


def panel():
    o = SimpleNamespace()
    o.content_stack = SimpleNamespace(setCurrentWidget=lambda widget: None)
    o.host = SimpleNamespace(winId=lambda: 99, width=lambda: 650, height=lambda: 400)
    o.title_label = SimpleNamespace(setText=lambda s: setattr(o, 'title', s),
                                    setToolTip=lambda s: setattr(o, 'tooltip', s))
    o.status_label = Status()
    o._external_key = None
    o._external_pending = None
    o._external_parked = {}
    o._obsidian_parked_vaults = {}
    o._external_timer = Timer()
    o._attached = None
    o._target = None
    o._obsidian_cli_busy = None
    o._obsidian_cli_ready = False
    o._obsidian_cli_queued = None
    o._obsidian_cli_token = None
    o._obsidian_cli_hwnd = None
    o._obsidian_cli_vault = 'vault-id'  # active A/B/C are in the same vault
    o._obsidian_main_probe_token = None
    o._obsidian_main_probe_busy = False
    o._obsidian_main_probe_attempts = 0
    o._probe_obsidian_main_window = lambda token: None
    o._sakura_switch_from = None
    o._sakura_baseline_pids = None
    o._sync_popout_button = lambda: None
    o.sakura_attached = lambda: False
    o._park_current = lambda: (_ for _ in ()).throw(AssertionError('unexpected park'))
    o._obsidian_switch_unavailable = lambda reason='': method('_obsidian_switch_unavailable')(o, reason)
    o.open_external = lambda target: method('open_external')(o, target)
    o._begin_obsidian_cli_bind = lambda target, hwnd: True
    o._switch_obsidian_inside = lambda target: True
    return o


def note(name):
    return ExternalPreviewTarget('obsidian', 'C:/vault/' + name + '.md')


def test_live_failed_cli_does_not_park_or_spawn_another_popup(monkeypatch):
    o = panel()
    o._external_key = note('A').key
    o._attached = Attached(101)
    opened = []
    monkeypatch.setattr(os, 'startfile', lambda *args: opened.append(args), raising=False)
    assert o.open_external(note('B')) is True  # pane stays alive and warns
    assert o._attached.hwnd == 101
    assert o._external_key == note('A').key
    assert not opened
    assert '新しい窓は作成しません' in o.status_label.text
    assert o.status_label.visible


def test_busy_switch_queues_last_request_without_opening_popup(monkeypatch):
    o = panel()
    o._external_key = note('A').key
    o._attached = Attached(101)
    o._obsidian_cli_busy = 'switch'
    monkeypatch.setattr(os, 'startfile', lambda *_: (_ for _ in ()).throw(AssertionError('second popup')), raising=False)
    assert o.open_external(note('B')) is True
    assert o.open_external(note('C')) is True
    assert o._obsidian_cli_queued == note('C')
    assert o._external_key == note('A').key


def test_pre_dock_double_click_is_queued_instead_of_spawned(monkeypatch):
    o = panel()
    o._external_key = note('A').key
    o._external_pending = (note('A'), frozenset(), None, time.monotonic())
    monkeypatch.setattr(os, 'startfile', lambda *_: (_ for _ in ()).throw(AssertionError('second popup')), raising=False)
    assert o.open_external(note('B'))
    assert o._obsidian_cli_queued == note('B')
    assert o._external_pending[0] == note('A')


def test_parked_popup_for_a_is_reused_for_b_and_bound_to_a(monkeypatch):
    import studio_win32_host
    o = panel()
    o._external_parked[note('A').key] = 101
    o._obsidian_parked_vaults[note('A').key] = 'vault-id'
    o._park_current = lambda: None  # no live editor to park
    opened = []
    binds = []
    monkeypatch.setattr(os, 'startfile', lambda *args: opened.append(args), raising=False)
    monkeypatch.setattr(studio_win32_host, 'AttachedStudioWindow', lambda hwnd, host: Attached(hwnd))
    o._begin_obsidian_cli_bind = lambda target, hwnd: binds.append((target, hwnd)) or True
    assert o.open_external(note('B')) is True
    assert opened == []
    assert len(binds) == 1 and binds[0][1] == 101
    assert binds[0][0].key == note('A').key
    assert o._obsidian_cli_queued == note('B')
    assert o._external_key == note('A').key
    assert o._external_parked == {}
    assert o._attached.hwnd == 101
    assert 'a.md' in o.title.lower()


def test_parked_reuse_with_unavailable_cli_cannot_spawn_another(monkeypatch):
    import studio_win32_host
    o = panel()
    o._external_parked[note('A').key] = 101
    o._obsidian_parked_vaults[note('A').key] = 'vault-id'
    o._park_current = lambda: None  # no live editor to park
    monkeypatch.setattr(os, 'startfile', lambda *_: (_ for _ in ()).throw(AssertionError('second popup')), raising=False)
    monkeypatch.setattr(studio_win32_host, 'AttachedStudioWindow', lambda hwnd, host: Attached(hwnd))
    o._begin_obsidian_cli_bind = lambda target, hwnd: False
    assert o.open_external(note('B')) is True
    assert o._external_key == note('A').key
    assert o._attached.hwnd == 101
    assert o.status_label.visible


def test_broken_parked_handle_is_kept_without_spawning(monkeypatch):
    import studio_win32_host
    o = panel()
    o._external_parked[note('A').key] = 101
    o._obsidian_parked_vaults[note('A').key] = 'vault-id'
    o._park_current = lambda: None  # no live editor to park
    monkeypatch.setattr(os, 'startfile', lambda *_: (_ for _ in ()).throw(AssertionError('second popup')), raising=False)
    def broken(*_): raise OSError('invalid HWND')
    monkeypatch.setattr(studio_win32_host, 'AttachedStudioWindow', broken)
    assert o.open_external(note('B')) is True
    assert o._external_parked == {note('A').key: 101}
    assert o._attached is None
    assert o.status_label.visible


def test_bind_failure_discards_queued_request_without_fallback():
    o = panel()
    o._external_key = note('A').key
    o._attached = Attached(101)
    o._obsidian_cli_busy = 'bind'
    o._obsidian_cli_token = 'safe'
    o._obsidian_cli_hwnd = 101
    o._obsidian_cli_queued = note('B')
    method('_on_obsidian_cli_completed')(o, 'bind', note('A'), 'FRB_NOT_UNIQUE', 101, 'safe')
    assert o._obsidian_cli_ready is False
    assert o._obsidian_cli_queued is None
    assert o.status_label.visible
    assert o._external_key == note('A').key


def test_bind_success_switches_latest_queued_in_same_window():
    o = panel()
    o._external_key = note('A').key
    o._attached = Attached(101)
    o._obsidian_cli_busy = 'bind'
    o._obsidian_cli_token = 'safe'
    o._obsidian_cli_hwnd = 101
    o._obsidian_cli_queued = note('B')
    switched = []
    o._switch_obsidian_inside = lambda target: switched.append(target) or True
    method('_on_obsidian_cli_completed')(o, 'bind', note('A'), 'FRB_BOUND', 101, 'safe')
    assert switched == [note('B')]
    assert o._external_key == note('A').key  # until CLI switch ack


def test_failed_switch_does_not_reopen_and_does_not_rename_old_note():
    o = panel()
    o._external_key = note('A').key
    o._attached = Attached(101)
    o._obsidian_cli_busy = 'switch'
    o._obsidian_cli_ready = True
    o._obsidian_cli_token = 'safe'
    o._obsidian_cli_hwnd = 101
    o._obsidian_cli_queued = note('C')
    o.title = 'Obsidian — A.md'
    method('_on_obsidian_cli_completed')(o, 'switch', note('B'), 'FRB_CLI_FAILED', 101, 'safe')
    assert o._external_key == note('A').key
    assert o._obsidian_cli_ready is False
    assert o._obsidian_cli_queued is None
    assert '切替完了を確認できません' in o.status_label.text


def test_first_request_one_open_uri_then_repeated_clicks_do_not_open_more(monkeypatch):
    import external_win32_host
    o = panel()
    o._park_current = lambda: None
    calls = []
    monkeypatch.setattr(os, 'startfile', lambda uri: calls.append(uri), raising=False)
    monkeypatch.setattr(external_win32_host, 'snapshot_editor_windows', lambda app: frozenset())
    monkeypatch.setattr(external_win32_host, 'snapshot_editor_process_ids', lambda app: frozenset())
    monkeypatch.setattr('obsidian_dock_bridge.registered_note', lambda path: ('vault-id', 'A.md'))
    monkeypatch.setattr('obsidian_dock_bridge.find_cli', lambda: 'Obsidian.com')
    assert o.open_external(note('A')) is True
    assert o.open_external(note('B')) is True
    assert o.open_external(note('C')) is True
    assert calls == ['obsidian://open?vault=vault-id']
    assert o._obsidian_cli_queued == note('C')


def test_ready_docked_popup_cannot_reopen_for_unsupported_vault(monkeypatch):
    o = panel()
    o._external_key = note('A').key
    o._attached = Attached(101)
    o._obsidian_cli_ready = True
    o._switch_obsidian_inside = lambda target: False  # wrong vault / no CLI
    monkeypatch.setattr(os, 'startfile', lambda *_: (_ for _ in ()).throw(AssertionError('second popup')), raising=False)
    assert o.open_external(note('B')) is True
    assert o._external_key == note('A').key
    assert o.status_label.visible


def test_bind_keeps_first_dock_double_click_queue(monkeypatch):
    import obsidian_dock_bridge
    o = panel()
    o._external_pending = (note('A'), frozenset(), None, time.monotonic())
    o._obsidian_cli_queued = note('B')
    o._reset_obsidian_cli = lambda: method('_reset_obsidian_cli')(o)
    operations = []
    o._run_obsidian_cli = lambda kind, target, vault, script, cli: operations.append((kind, target, vault, script, cli))
    monkeypatch.setattr(obsidian_dock_bridge, 'registered_note', lambda path: ('vault', 'A.md'))
    monkeypatch.setattr(obsidian_dock_bridge, 'find_cli', lambda: 'Obsidian.com')
    monkeypatch.setattr(obsidian_dock_bridge, 'bind_main_code', lambda path, token: 'JS')
    assert method('_begin_obsidian_cli_bind')(o, note('A'), 101)
    assert o._obsidian_cli_queued == note('B')
    assert operations[0][0:3] == ('bind', note('A'), 'vault')
    assert o._obsidian_cli_hwnd == 101
