"""Sakura tab/window reuse and Obsidian registered-vault safety.

These run without Windows, verifying state-machine contracts with faked HWNDs.
Real native drawing and persistence remain Windows acceptance checks.
"""
import ast
import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

from external_preview_route import (ExternalPreviewTarget, find_vault_root,
                                    registered_obsidian_vaults, external_preview_target)

SRC = Path(__file__).resolve().parents[1] / 'src'


def _panel_method(name):
    tree = ast.parse((SRC / 'studio_preview_panel.py').read_text(encoding='utf-8'))
    panel = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == 'StudioPreviewPanel')
    method = next(node for node in panel.body if isinstance(node, ast.FunctionDef)
                  and node.name == name)
    scope = {'Path': Path, 'subprocess': subprocess, 'time': time}
    exec(compile(ast.Module(body=[method], type_ignores=[]), f'<{name}>', 'exec'), scope)
    return scope[name]


class FakeTitle:
    def __init__(self):
        self.value = 'サクラエディタ — 1.txt'
        self.tooltip = ''
    def setText(self, value):
        self.value = value
    def text(self):
        return self.value
    def setToolTip(self, value):
        self.tooltip = value


class FakeTimer:
    def __init__(self):
        self.running = False
    def start(self):
        self.running = True
    def stop(self):
        self.running = False


class FakeStatus:
    def __init__(self):
        self.message = ''
        self.visible = False
    def setText(self, text):
        self.message = text
    def show(self):
        self.visible = True
    def hide(self):
        self.visible = False


def test_registered_vault_not_just_obsidian_folder(tmp_path, monkeypatch):
    appdata = tmp_path / 'AppData' / 'Roaming'
    registry = appdata / 'obsidian' / 'obsidian.json'
    registry.parent.mkdir(parents=True)
    valid = tmp_path / 'my notes'
    valid.mkdir()
    (valid / '.obsidian').mkdir()
    note = valid / 'test.md'
    note.write_text('test', encoding='utf-8')
    another = tmp_path / 'unregistered'
    another.mkdir()
    (another / '.obsidian').mkdir()
    unknown = another / 'unknown.md'
    unknown.write_text('test', encoding='utf-8')
    monkeypatch.setenv('APPDATA', str(appdata))
    # Merely placing .obsidian in a directory must never cause a modal error.
    assert registered_obsidian_vaults() == ()
    assert find_vault_root(note) is None
    assert external_preview_target({'_file': str(note)}).app == 'obsidian'
    registry.write_text(json.dumps({'vaults': {'123': {'path': str(valid), 'ts': 9}}}),
                        encoding='utf-8')
    assert find_vault_root(note) == valid
    assert external_preview_target({'_file': str(note)}).app == 'obsidian'
    assert find_vault_root(unknown) is None
    assert external_preview_target({'_file': str(unknown)}).app == 'obsidian'


def test_sakura_next_file_does_not_park_visible_editor(monkeypatch, tmp_path):
    import external_win32_host as host
    import external_preview_route as route
    monkeypatch.setattr(host, 'snapshot_editor_windows', lambda _: frozenset({100}))
    monkeypatch.setattr(host, 'snapshot_editor_process_ids', lambda _: frozenset({50}))
    target = ExternalPreviewTarget('sakura', str(tmp_path / '2.txt'), str(tmp_path / 'sakura.exe'))
    (tmp_path / 'sakura.exe').write_text('app')
    calls = []
    monkeypatch.setattr(subprocess, 'Popen', lambda args, cwd: calls.append((args, cwd)) or SimpleNamespace(pid=123))
    attach = SimpleNamespace(hwnd=100, attached=True)
    panel = SimpleNamespace(_external_pending=None, _external_key=('sakura', 'first'),
                            _attached=attach, title_label=FakeTitle(),
                            _external_timer=FakeTimer(), _sakura_switch_from=None,
                            status_label=FakeStatus())
    assert _panel_method('_open_sakura_next')(panel, target) is True
    assert panel._attached is attach
    assert panel._external_key == ('sakura', 'first')
    assert panel._sakura_switch_from == (('sakura', 'first'), 'サクラエディタ — 1.txt')
    assert calls[0][0][-1] == target.path
    assert panel._external_timer.running


def test_sakura_same_hwnd_tab_selection_is_not_reparented(monkeypatch, tmp_path):
    import external_win32_host as host
    target = ExternalPreviewTarget('sakura', str(tmp_path / '3.ini'), str(tmp_path / 'sakura.exe'))
    monkeypatch.setattr(host, 'find_new_editor_window', lambda *args: None)
    monkeypatch.setattr(host, 'editor_window_title', lambda hwnd: '3.ini - サクラエディタ')
    panel = SimpleNamespace(_external_pending=(target, frozenset(), 123, time.monotonic()),
                            _sakura_switch_from=(('sakura', '2'), 'サクラエディタ — 2.txt'),
                            _attached=SimpleNamespace(hwnd=100, attached=True),
                            _external_key=('sakura', '2'),
                            _external_timer=FakeTimer(), status_label=FakeStatus(),
                            title_label=FakeTitle())
    _panel_method('_poll_external')(panel)
    assert panel._external_pending is None
    assert panel._sakura_switch_from is None
    assert panel._external_key == target.key
    assert panel._attached.hwnd == 100


def test_sakura_new_hwnd_parks_previous_only_after_detection(monkeypatch, tmp_path):
    import external_win32_host as host
    import studio_win32_host as studio
    target = ExternalPreviewTarget('sakura', str(tmp_path / '3.txt'), str(tmp_path / 'sakura.exe'))
    monkeypatch.setattr(host, 'find_new_editor_window', lambda *args: 200)
    calls = []
    class NewWindow:
        def __init__(self, hwnd, host):
            calls.append(('attach', hwnd, host))
            self.hwnd = hwnd
        def resize(self, width, height):
            calls.append(('resize', width, height))
    monkeypatch.setattr(studio, 'AttachedStudioWindow', NewWindow)
    panel = SimpleNamespace(_external_pending=(target, frozenset({12}), 123, time.monotonic()),
                            _sakura_switch_from=(('sakura', '2'), 'サクラエディタ — 2.txt'),
                            _external_key=('sakura', '2'),
                            _attached=SimpleNamespace(hwnd=100, attached=True),
                            _external_timer=FakeTimer(), status_label=FakeStatus(),
                            host=SimpleNamespace(winId=lambda: 999, width=lambda: 700,
                                                 height=lambda: 400))
    def park():
        calls.append(('park', panel._attached.hwnd))
        panel._attached = None
        panel._external_key = None
    panel._park_external = park
    _panel_method('_poll_external')(panel)
    assert calls[0] == ('park', 100)
    assert calls[1] == ('attach', 200, 999)
    assert panel._external_key == target.key
    assert panel._attached.hwnd == 200
    assert panel._external_pending is None


def test_sakura_unconfirmed_switch_keeps_old_window(monkeypatch, tmp_path):
    import external_win32_host as host
    target = ExternalPreviewTarget('sakura', str(tmp_path / '3.txt'), str(tmp_path / 'sakura.exe'))
    monkeypatch.setattr(host, 'find_new_editor_window', lambda *args: None)
    monkeypatch.setattr(host, 'editor_window_title', lambda _: 'unrelated.txt - Sakura')
    attached = SimpleNamespace(hwnd=100, attached=True)
    panel = SimpleNamespace(_external_pending=(target, frozenset(), 123, time.monotonic()-8),
                            _sakura_switch_from=(('sakura', '2'), 'サクラエディタ — 2.txt'),
                            _external_key=('sakura', '2'), _attached=attached,
                            _external_timer=FakeTimer(), status_label=FakeStatus(),
                            title_label=FakeTitle())
    _panel_method('_poll_external')(panel)
    assert panel._attached is attached
    assert panel._external_key == ('sakura', '2')
    assert panel._external_pending is None
    assert '安全のため' in panel.status_label.message
