"""First Obsidian pop-out capture: safety / lifetime / no desktop hijack.

WinEvent delivery depends on Windows/Electron and requires manual acceptance;
these tests exercise the fail-closed state machine with a simulated event API.
"""
import ast
import time
from pathlib import Path
from types import SimpleNamespace

import external_win32_host as editors
from obsidian_quiet_window import (ObsidianQuietHandoff, _note_title_matches,
                                   _EVENT_OBJECT_SHOW, _EVENT_OBJECT_NAMECHANGE)

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'src' / 'studio_preview_panel.py'


class FakeEvents:
    def __init__(self):
        self.callback = None
        self.hidden = []
        self.restored = []
        self.stops = 0
        self.candidates = {201: True, 202: True}

    def start(self, callback):
        self.callback = callback
        return True

    def matches(self, hwnd, note):
        return self.candidates.get(hwnd, False)

    def hide(self, hwnd):
        self.hidden.append(hwnd)
        return True

    def reveal(self, hwnd):
        self.restored.append(hwnd)

    def stop(self):
        self.stops += 1

    def show_event(self, hwnd, event=_EVENT_OBJECT_SHOW, obj=0, child=0):
        self.callback(None, event, hwnd, obj, child, 42, 123)


def test_note_title_filter_is_exact_case_insensitive_and_rejects_empty():
    assert _note_title_matches('釣りノート.md - Obsidian', r'C:/vault/釣りノート.md')
    assert _note_title_matches('釣りノート - Obsidian', r'C:/vault/釣りノート.md')
    assert not _note_title_matches('Obsidian', r'C:/vault/釣りノート.md')
    assert not _note_title_matches('', r'C:/vault/釣りノート.md')


def test_only_new_matching_obisidian_hwnd_is_hidden():
    backend = FakeEvents()
    callbacks = []
    guard = ObsidianQuietHandoff('C:/vault/釣りノート.md', {100, 200},
                                 lambda: callbacks.append('poll'), backend=backend)
    assert guard.start()
    backend.show_event(200)  # existing user-owned popup
    backend.show_event(201, obj=-4)  # accessibility/client objects
    backend.show_event(201, child=5)
    backend.show_event(888)  # unrelated application or unrelated note
    assert backend.hidden == []
    backend.show_event(201)
    backend.show_event(201, event=_EVENT_OBJECT_NAMECHANGE)  # do not hide twice
    assert backend.hidden == [201]
    assert callbacks == ['poll']
    assert guard.hidden_hwnds == {201}
    guard.stop(restore=False)  # we successfully docked this HWND
    assert backend.stops == 1
    assert backend.restored == []
    assert guard.hidden_hwnds == set()


def test_hidden_window_is_restored_if_docking_fails():
    backend = FakeEvents()
    guard = ObsidianQuietHandoff('C:/vault/A.md', (), lambda: None, backend=backend)
    assert guard.start()
    backend.show_event(201)
    backend.show_event(202, event=_EVENT_OBJECT_NAMECHANGE)
    guard.stop(restore=True)
    assert sorted(backend.restored) == [201, 202]
    assert backend.stops == 1
    # No event callbacks after stop may hide anything else.
    backend.show_event(203)
    assert sorted(backend.hidden) == [201, 202]


def test_non_windows_or_failed_hook_does_not_block_original_poller():
    class NoHook(FakeEvents):
        def start(self, callback):
            return False
    guard = ObsidianQuietHandoff('C:/vault/A.md', (), lambda: None,
                                 backend=NoHook())
    assert guard.start() is False
    assert guard.hidden_hwnds == set()
    guard.stop(restore=True)


def test_find_new_editor_includes_only_early_hidden_allowlist(monkeypatch):
    from external_preview_route import ExternalPreviewTarget
    target = ExternalPreviewTarget('obsidian', 'C:/vault/New.md')
    calls = []
    def windows(app, include_hidden=False):
        calls.append((app, include_hidden))
        visible = [(100, 1, 'Existing.md - Obsidian')]
        hidden = [(101, 1, 'New.md - Obsidian'),
                  (102, 2, 'New.md - Obsidian')]  # unrelated hidden window
        return visible + hidden if include_hidden else visible
    monkeypatch.setattr(editors, 'editor_windows', windows)
    assert editors.find_new_editor_window(target, {100}) is None
    assert editors.find_new_editor_window(target, {100}, allowed_hidden_hwnds={101}) == 101
    assert editors.find_new_editor_window(target, {100}, allowed_hidden_hwnds={102}) == 102
    assert editors.find_new_editor_window(target, {100}, allowed_hidden_hwnds={101,102}) is None
    assert ('obsidian', True) in calls


def test_poll_and_cleanup_are_scoped_to_obsidian_only():
    tree = ast.parse(PANEL.read_text(encoding='utf-8'))
    panel = next(n for n in tree.body if isinstance(n, ast.ClassDef) and
                 n.name == 'StudioPreviewPanel')
    methods = {n.name: ast.get_source_segment(PANEL.read_text(encoding='utf-8'), n)
               for n in panel.body if isinstance(n, ast.FunctionDef)}
    assert 'ObsidianQuietHandoff' in methods['open_external']
    assert 'self._external_timer.setInterval(50 if target.app' in methods['open_external']
    assert 'guard.hidden_hwnds' in methods['_poll_external']
    assert 'self._stop_obsidian_quiet_guard(restore=False)' in methods['_poll_external']
    assert methods['_poll_external'].count('restore=True') >= 2
    assert 'restore=True' in methods['undock']
    assert 'restore=True' in methods['_park_external']
    assert '_switch_obsidian_inside(target)' in methods['open_external']
    assert 'setInterval(350)' in PANEL.read_text(encoding='utf-8')  # Sakura original
