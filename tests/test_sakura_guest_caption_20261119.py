"""Sakura Win32 titlebar contract: preserve the native caption, never SetParent."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from guest_window_overlay import GuestWindowOverlay, SakuraGuestOverlay
from studio_win32_host import (WS_CAPTION, WS_SYSMENU, WS_CHILD,
                               GWL_STYLE, SWP_FRAMECHANGED)
from test_obsidian_ime_overlay_20261119 import FakeWin32


def test_sakura_keeps_original_style_and_exstyle_through_attach_detach():
    from studio_win32_host import WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX
    api = FakeWin32()
    api.style |= WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    original = (api.style, api.exstyle)
    overlay = SakuraGuestOverlay(100, 200, user32=api)
    assert overlay.attached
    assert (api.style, api.exstyle) == original
    assert api.style & WS_CAPTION == WS_CAPTION
    assert not api.style & WS_CHILD
    # The classic Sakura GDI editor must never receive the Electron window
    # style rewrite that can disrupt rendering on its second/third tab.
    assert not any(call[0] == 'style' for call in api.calls)
    assert not any(call[0] == 'place' and (call[-1] & SWP_FRAMECHANGED)
                   for call in api.calls)
    assert not any(call[0] == 'parent' for call in api.calls)
    overlay.detach()
    assert (api.style, api.exstyle) == original


def test_vscode_and_obsidian_style_policy_still_strips_win32_caption():
    api = FakeWin32()
    overlay = GuestWindowOverlay(100, 200, user32=api)
    assert not api.style & WS_CAPTION
    assert not any(call[0] == 'place' and (call[-1] & SWP_FRAMECHANGED)
                   for call in api.calls)
    overlay.detach()


def test_sakura_preview_uses_specific_style_not_generic_chromium_style():
    src = (ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
    section = src[src.index('    def _open_sakura_guest('):src.index('    def pop_out_sakura_guest(')]
    assert section.count('SakuraGuestOverlay(') == 3
    assert 'GuestWindowOverlay(' not in section
    vscode = src[src.index('    def _open_vscode_guest('):src.index('    def _open_sakura_guest(')]
    assert 'GuestWindowOverlay(' in vscode
