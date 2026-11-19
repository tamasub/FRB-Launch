"""Regression for 001 -> 002 -> 003 -> 001 -> 002 on Sakura guest.

This tests Launch's ownership/selection transaction independently of Win32.
Windows live drawing and Sakura's native tab manager require a manual smoke.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import ast
import copy

# Extract the *actual* production method, so this logic can be tested even on
# CI/Linux without PySide6 or a Windows desktop.
module = ast.parse((ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8'))
klass = next(item for item in module.body if isinstance(item, ast.ClassDef)
             and item.name == 'StudioPreviewPanel')
method = copy.deepcopy(next(item for item in klass.body if isinstance(item, ast.FunctionDef)
                            and item.name == '_restore_known_sakura_guest'))
method.decorator_list = []
ns = {'Path': Path}
exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
             '<sakura-method>', 'exec'), ns)
restore_known_sakura_guest = ns['_restore_known_sakura_guest']
from external_preview_route import ExternalPreviewTarget
import external_win32_host
import guest_window_overlay


class Label:
    def __init__(self):
        self.value = ''
        self.hidden = False
    def setText(self, text):
        self.value = text
    def setToolTip(self, text):
        self.tip = text
    def hide(self):
        self.hidden = True


class FakeOverlay:
    titles = {}
    created = []
    def __init__(self, hwnd, host_hwnd):
        assert int(hwnd) in self.titles
        self.hwnd = int(hwnd)
        self.host_hwnd = host_hwnd
        self.u = SimpleNamespace(IsWindow=lambda hwnd: hwnd in FakeOverlay.titles)
        self.attached = True
        self.is_ime_overlay = True
        self.created.append(int(hwnd))
    def resize(self, width, height):
        self.size = width, height
    def detach(self, *, foreground=False, show_window=False):
        self.attached = False


def make_panel():
    panel = SimpleNamespace(
        _attached=FakeOverlay(303, 2),
        _external_key=('sakura', 'c:/docs/003.txt'),
        _external_parked={
            ('sakura', 'c:/docs/001.txt'): 301,
            ('sakura', 'c:/docs/002.txt'): 302,
        },
        host=SimpleNamespace(winId=lambda: 2, width=lambda: 900, height=lambda: 600),
        title_label=Label(), status_label=Label(),
        _sync_popout_button=lambda: None,
        _schedule_sakura_guest_repaint=lambda *args: None,
    )
    return panel


def test_revisit_two_older_tabs_without_launching_another_editor(monkeypatch):
    FakeOverlay.titles = {301: 'C:/docs/001.txt - サクラエディタ',
                          302: 'C:/docs/002.txt - サクラエディタ',
                          303: 'C:/docs/003.txt - サクラエディタ'}
    FakeOverlay.created = []
    monkeypatch.setattr(guest_window_overlay, 'SakuraGuestOverlay', FakeOverlay)
    monkeypatch.setattr(external_win32_host, 'editor_window_title',
                        lambda hwnd: FakeOverlay.titles.get(hwnd, ''))
    panel = make_panel()
    FakeOverlay.created.clear()
    first = ExternalPreviewTarget('sakura', 'C:/docs/001.txt')
    second = ExternalPreviewTarget('sakura', 'C:/docs/002.txt')
    assert restore_known_sakura_guest(panel, first)
    assert panel._external_key == first.key
    assert panel._attached.hwnd == 301
    assert panel._external_parked[('sakura', 'c:/docs/003.txt')] == 303
    assert restore_known_sakura_guest(panel, second)
    assert panel._external_key == second.key
    assert panel._attached.hwnd == 302
    assert panel._external_parked[first.key] == 301
    assert FakeOverlay.created == [301, 302]
    assert panel.title_label.value.endswith('002.txt')


def test_unknown_or_retargeted_hwnd_must_never_be_adopted(monkeypatch):
    FakeOverlay.titles = {301: 'different.txt - サクラエディタ',
                          302: 'C:/docs/002.txt - サクラエディタ',
                          303: 'C:/docs/003.txt - サクラエディタ'}
    FakeOverlay.created = []
    monkeypatch.setattr(guest_window_overlay, 'SakuraGuestOverlay', FakeOverlay)
    monkeypatch.setattr(external_win32_host, 'editor_window_title',
                        lambda hwnd: FakeOverlay.titles.get(hwnd, ''))
    panel = make_panel()
    FakeOverlay.created.clear()
    unknown = ExternalPreviewTarget('sakura', 'C:/docs/004.txt')
    stale = ExternalPreviewTarget('sakura', 'C:/docs/001.txt')
    assert not restore_known_sakura_guest(panel, unknown)
    assert not restore_known_sakura_guest(panel, stale)
    assert panel._external_key == ('sakura', 'c:/docs/003.txt')
    assert panel._attached.hwnd == 303
    assert FakeOverlay.created == []
