"""Sakura native desktop release: no Electron style rewrite, no GDI blank panes.

Win32 call-sequence checks use a fake API and run cross-platform. They do not
pretend to verify Sakura's real pixels; that needs the Windows acceptance test.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from guest_window_overlay import SakuraGuestOverlay
from studio_win32_host import (GWL_STYLE, GWL_EXSTYLE, WS_CAPTION,
                               SWP_FRAMECHANGED, RDW_ALLCHILDREN, RDW_FRAME,
                               RDW_INVALIDATE)
from test_obsidian_ime_overlay_20261119 import FakeWin32, Fn


class RecorderWin32(FakeWin32):
    def __init__(self):
        super().__init__()
        self.RedrawWindow = Fn(self.redraw)
        self.fail_pos = False

    def redraw(self, hwnd, region, rect, flags):
        self.calls.append(('redraw', hwnd, flags))
        return True

    def SetWindowPos(self, hwnd, after, x, y, w, h, flags):
        self.calls.append(('place', hwnd, after, x, y, w, h, flags))
        if not self.fail_pos and flags & 0x0080:  # SWP_HIDEWINDOW
            self.visible = False
        return not self.fail_pos


def test_desktop_release_restores_geometry_without_hiding_or_rewriting_native_frame():
    api = RecorderWin32()
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    assert overlay.attached
    assert api.style & WS_CAPTION
    api.calls.clear()

    overlay.detach(foreground=False, show_window=True)

    assert not overlay.attached
    assert not any(c[0] == 'style' for c in api.calls)
    assert not any(c == ('show', 0) for c in api.calls)  # no hide/show blink
    assert not any(c[0] == 'foreground' for c in api.calls)
    assert not any(c[0] == 'parent' for c in api.calls)
    desktop = [c for c in api.calls if c[0] == 'place']
    assert len(desktop) == 1
    assert desktop[0][3:7] == (100, 100, 900, 700)
    assert not desktop[0][-1] & SWP_FRAMECHANGED
    assert ('show', 4) in api.calls
    redraw = [c for c in api.calls if c[0] == 'redraw']
    assert len(redraw) == 1
    assert redraw[0][2] & RDW_ALLCHILDREN
    assert redraw[0][2] & RDW_FRAME
    assert redraw[0][2] & RDW_INVALIDATE
    assert api.visible


def test_hidden_parking_does_not_flash_or_immediately_repaint():
    api = RecorderWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.calls.clear()
    guest.detach(foreground=False, show_window=False)
    assert not guest.attached
    assert ('show', 0) not in api.calls  # atomic hide via SetWindowPos
    assert any(c[0] == 'place' and c[-1] & 0x0080 for c in api.calls)
    # A hidden parked editor must not repaint itself, but Launch must
    # invalidate the newly exposed backing area (including its header).
    assert all(c[1] != guest.hwnd for c in api.calls if c[0] == 'redraw')
    assert not any(c[0] == 'style' for c in api.calls)
    assert not api.visible


def test_only_real_style_drift_requests_frame_change():
    api = RecorderWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    original_style = api.style
    api.style &= ~WS_CAPTION  # simulate an externally altered native style
    api.calls.clear()
    guest.detach(foreground=False, show_window=True)
    assert api.style == original_style
    assert any(c[0] == 'style' and c[1] == GWL_STYLE for c in api.calls)
    assert any(c[0] == 'place' and (c[-1] & SWP_FRAMECHANGED) for c in api.calls)


def test_failed_geometry_restore_retains_attached_ownership():
    api = RecorderWin32()
    guest = SakuraGuestOverlay(100, 200, user32=api)
    api.fail_pos = True
    try:
        guest.detach(foreground=False, show_window=True)
        assert False, 'expected restore failure'
    except OSError:
        pass
    assert guest.attached


def _studio_method(name, globals_extra=None):
    src = (ROOT/'src'/'studio_preview_panel.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'StudioPreviewPanel')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    env = dict(globals_extra or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[])),
                 '<sakura-popout>', 'exec'), env)
    return env[name]


def test_delayed_redraw_after_browser_reflow_only_for_parked_same_hwnd():
    scheduled = []
    class Timer:
        @staticmethod
        def singleShot(delay, callback): scheduled.append((delay, callback))
    redraws = []
    guest = SimpleNamespace(attached=False, refresh_native_frame=lambda: redraws.append('paint'))
    key = ('sakura', 'c:/docs/001.txt')
    panel = SimpleNamespace(_external_parked={key:100})
    _studio_method('_schedule_sakura_desktop_repaint', {'QTimer':Timer})(panel,guest,key,100)
    assert [delay for delay, _ in scheduled] == [120,360]
    scheduled[0][1]()
    assert redraws == ['paint']
    panel._external_parked.pop(key)  # re-docked: do not repaint desktop
    scheduled[1][1]()
    assert redraws == ['paint']


def test_new_guest_reuses_original_native_caption_after_popout():
    api = RecorderWin32()
    first = SakuraGuestOverlay(100, 200, user32=api)
    first.detach(foreground=False, show_window=True)
    second = SakuraGuestOverlay(100, 200, user32=api)
    assert second.attached
    assert api.style & WS_CAPTION
    assert not any(c[0] == 'style' for c in api.calls)
    second.detach(foreground=False, show_window=True)
