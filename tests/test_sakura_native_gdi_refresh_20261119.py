"""Regression: native Sakura tab handoff must repaint without style/parent changes."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from guest_window_overlay import SakuraGuestOverlay
from studio_win32_host import RDW_INVALIDATE, RDW_ALLCHILDREN
from test_obsidian_ime_overlay_20261119 import FakeWin32, Fn


def test_sakura_repaints_all_native_children_without_data_or_focus_changes():
    api = FakeWin32()
    def redraw(hwnd, _region, _rect, flags):
        api.calls.append(('redraw', hwnd, flags))
        return True
    api.RedrawWindow = Fn(redraw)
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    assert overlay.refresh_document()
    redraw_calls = [call for call in api.calls if call[0] == 'redraw']
    assert len(redraw_calls) == 1
    assert redraw_calls[0][1] == 100
    assert redraw_calls[0][2] & RDW_INVALIDATE
    assert redraw_calls[0][2] & RDW_ALLCHILDREN
    assert not any(call[0] == 'foreground' for call in api.calls)
    assert not any(call[0] == 'style' for call in api.calls)
    overlay.detach()
    # A visible native desktop release deliberately repaints the full frame.
    after_detach = len([call for call in api.calls if call[0] == 'redraw'])
    assert after_detach == 2
    assert overlay.refresh_document() is False
    assert len([call for call in api.calls if call[0] == 'redraw']) == after_detach


def test_all_sakura_new_window_and_same_window_switches_schedule_repaint():
    source = (ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
    ast.parse(source)
    section = source.split('    def _poll_sakura_guest(self):', 1)[1].split(
        '    def pop_out_sakura_guest(self):', 1)[0]
    # New initial HWND, new HWND on switch and SAME HWND tab switch.
    assert section.count('self._schedule_sakura_guest_repaint(') == 3
    helper = source.split('    def _schedule_sakura_guest_repaint(', 1)[1].split(
        '    def _poll_sakura_guest(self):', 1)[0]
    assert 'self._external_key != key' in helper
    assert 'int(attached.hwnd) != int(hwnd)' in helper
    assert 'QTimer.singleShot(200, refresh)' in helper
    assert '.SetParent(' not in helper
