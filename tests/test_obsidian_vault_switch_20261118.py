"""Multi-vault handoff regression: no unrelated HWND, WM_CLOSE or pop-out.

AST-executed methods simulate Qt panel transitions on Linux; actual Windows
Obsidian native style, restore and CLI are verified only on the user's PC.
"""
import ast
import os
import time
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

from external_preview_route import ExternalPreviewTarget

SOURCE = (Path(__file__).resolve().parents[1] / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
PANEL = next(x for x in TREE.body if isinstance(x, ast.ClassDef) and x.name == 'StudioPreviewPanel')


def m(name):
    f = next(x for x in PANEL.body if isinstance(x, ast.FunctionDef) and x.name == name)
    g = {'Path': Path, 'os': os, 'time': time, 'subprocess': subprocess, 'uuid': uuid}
    exec(compile(ast.Module(body=[f], type_ignores=[]), name, 'exec'), g)
    return g[name]


class Attachment:
    def __init__(self, hwnd, host=None, fail_detach=False):
        self.hwnd = hwnd
        self.attached = True
        self.fail_detach = fail_detach
        self.resizes = []
        self.releases = []
    def resize(self, w, h): self.resizes.append((w, h))
    def detach(self, **kw):
        if self.fail_detach: raise OSError('fake SetParent failure')
        self.releases.append(kw)
        self.attached = False


class Text:
    def __init__(self): self.text = ''; self.visible = False
    def setText(self, value): self.text = value
    def setToolTip(self, value): self.tooltip = value
    def show(self): self.visible = True
    def hide(self): self.visible = False


class Timer:
    def __init__(self): self.running = False
    def stop(self): self.running = False
    def start(self): self.running = True


def note(vault, name):
    return ExternalPreviewTarget('obsidian', f'C:/{vault}/{name}.md')


def fixture(monkeypatch, vault_ids=None):
    import obsidian_dock_bridge as bridge
    import external_win32_host as windows
    import studio_win32_host as native
    vault_ids = vault_ids or {'A': 'id-A', 'B': 'id-B'}
    monkeypatch.setattr(bridge, 'registered_note',
                        lambda path: (vault_ids[Path(path).parent.name], Path(path).name)
                        if Path(path).parent.name in vault_ids else None)
    monkeypatch.setattr(bridge, 'find_cli', lambda: 'Obsidian.com')
    monkeypatch.setattr(windows, 'snapshot_editor_windows', lambda app: frozenset())
    monkeypatch.setattr(windows, 'snapshot_editor_process_ids', lambda app: frozenset())
    native_attach = []
    monkeypatch.setattr(native, 'AttachedStudioWindow',
                        lambda hwnd, host: native_attach.append(Attachment(hwnd, host)) or native_attach[-1])
    startfiles = []
    monkeypatch.setattr(os, 'startfile', lambda uri: startfiles.append(uri), raising=False)
    obj = SimpleNamespace()
    obj.content_stack = SimpleNamespace(setCurrentWidget=lambda x: None)
    obj.host = SimpleNamespace(winId=lambda: 444, width=lambda: 660, height=lambda: 500)
    obj.status_label = Text()
    obj.title_label = Text()
    obj._external_key = None
    obj._external_pending = None
    obj._external_parked = {}
    obj._obsidian_parked_vaults = {}
    obj._attached = None
    obj._target = None
    obj._external_timer = Timer()
    obj._obsidian_cli_vault = None
    obj._obsidian_cli_token = None
    obj._obsidian_cli_hwnd = None
    obj._obsidian_cli_ready = False
    obj._obsidian_cli_busy = None
    obj._obsidian_cli_queued = None
    obj._obsidian_main_probe_token = None
    obj._obsidian_main_probe_busy = False
    obj._obsidian_main_probe_attempts = 0
    obj._obsidian_main_open_issued = False
    obj._sakura_switch_from = None
    obj._sakura_baseline_pids = None
    obj._sync_popout_button = lambda: None
    obj._park_current = lambda: None
    obj._probe_obsidian_main_window = lambda token: None
    obj._begin_obsidian_cli_bind = lambda file, hwnd: True
    switches = []
    obj._switch_obsidian_inside = lambda file: switches.append(file) or True
    obj.sakura_attached = lambda: False
    obj._obsidian_switch_unavailable = lambda reason='': m('_obsidian_switch_unavailable')(obj, reason)
    obj._reset_obsidian_cli = lambda: m('_reset_obsidian_cli')(obj)
    obj._release_obsidian_for_vault_change = lambda: m('_release_obsidian_for_vault_change')(obj)
    obj.open_external = lambda target: m('open_external')(obj, target)
    return obj, startfiles, native_attach, switches


def live(obj, vault='A', name='first'):
    target = note(vault, name)
    obj._external_key = target.key
    obj._attached = Attachment(77)
    obj._obsidian_cli_vault = f'id-{vault}'
    obj._obsidian_cli_ready = True
    obj._obsidian_cli_hwnd = 77
    obj._obsidian_cli_token = 'session'
    return target


def test_different_vault_releases_old_main_and_starts_unique_probe(monkeypatch):
    obj, startfiles, native_attach, switches = fixture(monkeypatch)
    old = live(obj)
    old_hwnd = obj._attached
    assert obj.open_external(note('B','second')) is True
    assert old_hwnd.releases == [{'foreground': False, 'show_window': True}]
    assert obj._attached is None
    assert obj._obsidian_cli_vault is None
    assert obj._external_pending[0].key == note('B','second').key
    assert obj._external_key == note('B','second').key
    assert startfiles == ['obsidian://open?vault=id-B']
    assert native_attach == []
    assert switches == []


def test_same_vault_switch_keeps_one_main_window(monkeypatch):
    obj, startfiles, _, switches = fixture(monkeypatch)
    live(obj)
    old_hwnd = obj._attached
    assert obj.open_external(note('A','next')) is True
    assert old_hwnd.releases == []
    assert switches == [note('A','next')]
    assert startfiles == []


def test_different_vault_with_busy_cli_queues_latest_then_release(monkeypatch):
    obj, startfiles, _, _ = fixture(monkeypatch)
    live(obj)
    old_hwnd = obj._attached
    obj._obsidian_cli_busy = 'switch'
    assert obj.open_external(note('B','second'))
    assert obj._obsidian_cli_queued == note('B','second')
    assert old_hwnd.releases == [] and startfiles == []
    obj._obsidian_cli_busy = None
    assert obj.open_external(obj._obsidian_cli_queued)
    assert old_hwnd.releases == [{'foreground': False, 'show_window': True}]
    assert startfiles == ['obsidian://open?vault=id-B']


def test_unknown_vault_leaves_current_window_intact(monkeypatch):
    obj, startfiles, _, _ = fixture(monkeypatch)
    live(obj)
    old_hwnd = obj._attached
    assert obj.open_external(note('unknown','bad')) is True
    assert old_hwnd.releases == [] and obj._external_key == note('A','first').key
    assert obj._attached is old_hwnd and startfiles == []
    assert obj.status_label.visible and '未登録' in obj.status_label.text


def test_restore_error_never_starts_new_vault_or_discards_old(monkeypatch):
    obj, startfiles, _, _ = fixture(monkeypatch)
    live(obj)
    obj._attached.fail_detach = True
    assert obj.open_external(note('B','second')) is True
    assert obj._external_key == note('A','first').key
    assert obj._attached.attached and obj._external_pending is None
    assert not startfiles
    assert '安全に復元できません' in obj.status_label.text


def test_parked_other_vault_not_reparented_on_studio_to_obsidian(monkeypatch):
    obj, startfiles, native_attach, _ = fixture(monkeypatch)
    obj._external_parked = {note('A','first').key: 101}
    obj._obsidian_parked_vaults = {note('A','first').key: 'id-A'}
    assert obj.open_external(note('B','second')) is True
    assert startfiles == ['obsidian://open?vault=id-B']
    assert native_attach == []
    assert obj._external_parked == {note('A','first').key: 101}


def test_parked_matching_vault_is_reused_without_new_window(monkeypatch):
    obj, startfiles, native_attach, _ = fixture(monkeypatch)
    obj._external_parked = {note('A','first').key: 101}
    obj._obsidian_parked_vaults = {note('A','first').key: 'id-A'}
    binds = []
    obj._begin_obsidian_cli_bind = lambda t, h: binds.append((t, h)) or True
    assert obj.open_external(note('A','second')) is True
    assert startfiles == []
    assert len(native_attach) == 1 and native_attach[0].hwnd == 101
    assert len(binds) == 1 and binds[0][0].key == note('A','first').key and binds[0][1] == 101
    assert obj._obsidian_cli_queued == note('A','second')
    assert obj._external_parked == {} and obj._obsidian_parked_vaults == {}


def test_failed_cached_hwnd_reattach_retains_registered_vault(monkeypatch):
    import studio_win32_host as native
    obj, startfiles, _, _ = fixture(monkeypatch)
    obj._external_parked = {note('A','first').key: 101}
    obj._obsidian_parked_vaults = {note('A','first').key: 'id-A'}
    monkeypatch.setattr(native,'AttachedStudioWindow',lambda *a: (_ for _ in ()).throw(OSError('bad HWND')))
    assert obj.open_external(note('A','second')) is True
    assert obj._external_parked == {note('A','first').key: 101}
    assert obj._obsidian_parked_vaults == {note('A','first').key: 'id-A'}
    assert startfiles == []
