"""Regression for third-column desktop release and main search history density.

The Win32 HWND operations are mocked; final Electron/WinForms visual behavior
still requires a Windows desktop acceptance pass.
"""
from pathlib import Path
import sys
from ctypes import wintypes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from studio_win32_host import (AttachedStudioWindow, WS_POPUP, WS_CAPTION,
                               WS_EX_APPWINDOW, release_obsidian_desktop_z_order)
from launch_appearance import history_popup_qss


class FakeUser32:
    def __init__(self):
        self.calls = []
        self.client_rect = (820, 220, 520, 610)

    def IsWindow(self, hwnd):
        return hwnd == 44

    def GetWindowRect(self, hwnd, out):
        assert hwnd == 44
        x, y, w, h = self.client_rect
        rect = out._obj
        rect.left, rect.top, rect.right, rect.bottom = x, y, x + w, y + h
        return True

    def ShowWindow(self, hwnd, code):
        self.calls.append(('show', code))
        return True

    def SetParent(self, hwnd, parent):
        self.calls.append(('parent', parent))
        return 0

    def SetWindowLongPtrW(self, hwnd, index, style):
        self.calls.append(('style', index, style))
        return 1

    def SetWindowPos(self, hwnd, after, x, y, width, height, flags):
        self.calls.append(('place', after, x, y, width, height, flags))
        return True

    def RedrawWindow(self, hwnd, rect, region, flags):
        self.calls.append(('redraw', flags))
        return True

    def SetForegroundWindow(self, hwnd):
        self.calls.append(('foreground', hwnd))
        return True


def attached(u):
    obj = object.__new__(AttachedStudioWindow)
    obj.u = u
    obj.hwnd = 44
    obj.attached = True
    obj.original_parent = 0
    obj.original_style = WS_POPUP | WS_CAPTION
    obj.original_exstyle = WS_EX_APPWINDOW
    obj.original_rect = (150, 90, 1500, 970)
    return obj


def test_studio_explicit_popout_retains_docked_screen_dimensions():
    u = FakeUser32()
    a = attached(u)
    a.detach(foreground=True, show_window=True, keep_docked_size=True)
    assert not a.attached
    assert ('place', 0, 820, 220, 520, 610, 0x0004 | 0x0020 | 0x0040) in u.calls
    assert ('place', 0, 150, 90, 1500, 970, 0x0004 | 0x0020 | 0x0040) not in u.calls


def test_regular_detach_keeps_existing_saved_desktop_geometry():
    u = FakeUser32()
    a = attached(u)
    a.detach(foreground=True, show_window=True)
    assert ('place', 0, 150, 90, 1500, 970, 0x0004 | 0x0020 | 0x0040) in u.calls
    assert ('place', 0, 820, 220, 520, 610, 0x0004 | 0x0020 | 0x0040) not in u.calls


def test_obsidian_explicit_popout_demotes_from_topmost_without_activation():
    u = FakeUser32()
    assert release_obsidian_desktop_z_order(44, user32=u)
    assert u.calls == [('place', -2, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)]
    assert not release_obsidian_desktop_z_order(55, user32=u)
    assert len(u.calls) == 1


def test_obsidian_both_popout_and_close_paths_apply_normal_zorder():
    panel = (ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
    assert panel.count('release_obsidian_desktop_z_order(attached.hwnd, user32=attached.u)') == 2
    assert "if self._external_key[0] == 'obsidian' and hasattr(attached, 'u'):" in panel
    vscode = panel.split('    def pop_out_vscode(self):', 1)[1].split('    def pop_out_obsidian(self):', 1)[0]
    assert 'release_obsidian_desktop_z_order' not in vscode
    obsidian = panel.split('    def pop_out_obsidian(self):', 1)[1].split('    def pop_out_studio(self):', 1)[0]
    assert 'release_obsidian_desktop_z_order' in obsidian


def test_search_history_matches_list_typography_and_density():
    normal = history_popup_qss('light', height=29, vertical_padding=3, padding=7, font_size=12)
    compact = history_popup_qss('dark', height=23, vertical_padding=1, padding=7, font_size=12)
    for qss in (normal, compact):
        assert 'font-size:12px' in qss
        assert 'font-family:"Yu Gothic UI"' in qss
        assert 'padding:' in qss
    assert 'min-height:29px' in normal
    assert 'padding:3px 7px' in normal
    assert 'min-height:23px' in compact
    assert 'padding:1px 7px' in compact
    app = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    assert app.count('height=23 if compact else 29') == 2
    assert app.count('font_size=12') >= 2
