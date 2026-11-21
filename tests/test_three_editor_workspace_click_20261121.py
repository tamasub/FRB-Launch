"""Explicit mouse-release activation of non-parented editor guest workspaces.

Fake Win32 stack models chrome occlusion and the three-editor native overlay
contract. Actual foreground ownership and IME must also be checked on Windows.
"""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'src'))
sys.path.insert(0, str(HERE / 'tests'))
from test_guest_overlay_zorder_and_popout_20261119 import (
    Desktop, ObsidianImeOverlay, GUEST, HOST, LAUNCH, CHROME,
)
from guest_window_overlay import GuestWindowOverlay, SakuraGuestOverlay
from obsidian_ime_overlay import SWP_NOACTIVATE, WS_EX_TOPMOST

class ClickDesktop(Desktop):
    def __init__(self):
        super().__init__()
        self.hit = GUEST
        self.children = {601: GUEST, 602: GUEST}
    def WindowFromPoint(self, point):
        return self.hit
    def IsChild(self, hwnd, child):
        return self.children.get(child) == hwnd
    def IsWindow(self, hwnd):
        return hwnd in self.children or super().IsWindow(hwnd)


def editor_overlay(cls):
    api = ClickDesktop()
    overlay = cls(GUEST, HOST, user32=api)
    # Normal background case: Chrome above guest, guest above Launch.
    assert api.stack.index(CHROME) < api.stack.index(GUEST) < api.stack.index(LAUNCH)
    return api, overlay


def test_all_three_guests_raise_launch_when_genuinely_clicked():
    for cls in (ObsidianImeOverlay, GuestWindowOverlay, SakuraGuestOverlay):
        api, overlay = editor_overlay(cls)
        api.foreground = GUEST
        assert overlay.raise_workspace_from_guest_click(100, 200) is True
        assert api.stack.index(GUEST) < api.stack.index(LAUNCH) < api.stack.index(CHROME)
        assert api.foreground == GUEST  # focus/IME remains with editor
        assert not any(call[0] == 'foreground' for call in api.calls)
        assert not api.exstyles[GUEST] & WS_EX_TOPMOST
        assert not api.exstyles[LAUNCH] & WS_EX_TOPMOST
        assert any(call[0] == 'place' and call[1] == LAUNCH and
                   call[-1] & SWP_NOACTIVATE for call in api.calls)


def test_child_pane_click_works_for_sakura_but_other_windows_do_not():
    api, overlay = editor_overlay(SakuraGuestOverlay)
    api.hit = 601  # Sakura GDI editor child
    assert overlay.raise_workspace_from_guest_click(10, 20)
    api, overlay = editor_overlay(SakuraGuestOverlay)
    for other in (CHROME, LAUNCH, 0):
        api.hit = other
        before = list(api.calls)
        assert not overlay.raise_workspace_from_guest_click(10, 20)
        assert api.calls == before


def test_polling_does_not_raise_background_launch_without_click():
    api, overlay = editor_overlay(GuestWindowOverlay)
    api.foreground = CHROME
    before = list(api.calls)
    for _ in range(10):
        overlay.sync()
    assert api.calls == before
    assert api.stack.index(CHROME) < api.stack.index(LAUNCH)


def test_click_is_not_processed_when_launch_minimized_or_guest_detached():
    api, overlay = editor_overlay(ObsidianImeOverlay)
    api.iconic = True
    assert not overlay.raise_workspace_from_guest_click(10, 20)
    api.iconic = False
    overlay.detach(foreground=False, show_window=False)
    assert not overlay.raise_workspace_from_guest_click(10, 20)


def test_native_history_popup_keeps_priority_over_guest_after_click():
    popup = 900
    class PopupDesktop(ClickDesktop):
        def IsWindow(self, hwnd):
            return hwnd == popup or super().IsWindow(hwnd)
    api = PopupDesktop()
    overlay = ObsidianImeOverlay(GUEST, HOST, user32=api)
    api.stack.insert(api.stack.index(GUEST), popup)
    api.exstyles[popup] = 0
    api.foreground = GUEST
    overlay.sync(popup_hwnds=(popup,))
    # Mouse lands on the editor, not on the popup.
    assert overlay.raise_workspace_from_guest_click(12, 32)
    assert api.stack.index(popup) < api.stack.index(GUEST) < api.stack.index(LAUNCH)


def panel_method():
    src = (HERE / 'src/studio_preview_panel.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'StudioPreviewPanel')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == 'focus_external_after_native_click')
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 'studio_preview_panel.py', 'exec'), scope)
    return scope[fn.name]


def test_panel_routes_all_three_editor_guests_through_same_handler():
    method = panel_method()
    for app in ('obsidian', 'vscode', 'sakura'):
        calls = []
        obj = NS(_external_key=(app, 'document'), _attached=NS(
                 is_ime_overlay=True, raise_workspace_from_guest_click=lambda x, y:
                 calls.append((x, y)) or True),
                 external_embedded_active=lambda: True)
        assert method(obj, 121, 203) is True
        assert calls == [(121, 203)]
    # NativeShell Studio does not use this overlay path.
    obj = NS(_external_key=('studio', 'file'),
             _attached=NS(is_ime_overlay=False),
             external_embedded_active=lambda: True)
    assert method(obj, 121, 203) is False


def test_no_activation_on_explicit_click_or_implicit_timers():
    code = (HERE / 'src/obsidian_ime_overlay.py').read_text(encoding='utf-8')
    fn = code.split('    def raise_workspace_from_guest_click(')[1].split('    def resize(')[0]
    assert 'SetForegroundWindow' not in fn
    assert 'SWP_NOACTIVATE' in fn
    panel = (HERE / 'src/studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'return bool(attached.raise_workspace_from_guest_click(x, y))' in panel
    app = (HERE / 'src/app.py').read_text(encoding='utf-8')
    assert 'preview.focus_external_after_native_click(x, y)' in app
