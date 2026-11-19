"""Obsidian-only, opt-in non-parenting window overlay contract (mock Win32)."""
import os
import sys
from pathlib import Path
from ctypes import wintypes
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from obsidian_ime_overlay import ObsidianImeOverlay, overlay_enabled
from studio_win32_host import WS_CHILD, WS_POPUP, GWL_STYLE, GWL_EXSTYLE


class Fn:
    def __init__(self, f): self.f = f
    def __call__(self, *args): return self.f(*args)


class FakeWin32:
    def __init__(self):
        self.style = WS_POPUP | 0x10000000 | 0x00C00000
        self.exstyle = 0x00040000
        self.visible = True
        self.host_rect = (800, 300, 600, 480)
        self.front = 999
        self.iconic = False
        self.foreground_pid = 333
        self.calls = []
        self.ClientToScreen = Fn(self.client_to_screen)
        self.GetClientRect = Fn(self.get_client_rect)
        self.IsIconic = Fn(lambda hwnd: self.iconic)
        self.GetWindow = Fn(lambda hwnd, cmd: 100 if self.front == 999 else self.front)

    def IsWindow(self, hwnd): return bool(hwnd in (100, 200, 999, 888, 777))
    def GetWindowLongPtrW(self, hwnd, index):
        return self.style if index == GWL_STYLE else self.exstyle
    def SetWindowLongPtrW(self, hwnd, index, value):
        self.calls.append(('style', index, value))
        if index == GWL_STYLE: self.style = value
        else: self.exstyle = value
        return 1
    def GetWindowRect(self, hwnd, out):
        rect=out._obj
        rect.left,rect.top,rect.right,rect.bottom=100,100,1000,800
        return True
    def GetAncestor(self, hwnd, kind): return 999
    def GetForegroundWindow(self): return self.front
    def GetWindowThreadProcessId(self, hwnd, out):
        if out is not None:
            out._obj.value = 333 if hwnd == 100 else self.foreground_pid
        return 1
    def client_to_screen(self, hwnd, out):
        out._obj.x,self_x = self.host_rect[0],0
        out._obj.y = self.host_rect[1]
        return True
    def get_client_rect(self, hwnd, out):
        r=out._obj
        r.left,r.top=0,0
        r.right,r.bottom=self.host_rect[2:]
        return True
    def SetWindowPos(self, hwnd, after, x,y,w,h, flags):
        self.calls.append(('place', hwnd, after, x,y,w,h,flags))
        if flags & 0x40: self.visible = True
        return True
    def ShowWindow(self, hwnd, style):
        self.calls.append(('show', style))
        self.visible = (style!=0)
        return True
    def SetForegroundWindow(self, hwnd):
        self.calls.append(('foreground',hwnd))
        return True


def test_overlay_is_opt_in_by_environment():
    with patch.dict(os.environ, {'FRB_OBSIDIAN_IME_OVERLAY':'1'}):
        assert overlay_enabled()
    with patch.dict(os.environ, {'FRB_OBSIDIAN_IME_OVERLAY':'0'}):
        assert not overlay_enabled()


def test_overlay_does_not_call_setparent_and_remains_toplevel():
    u=FakeWin32()
    overlay=ObsidianImeOverlay(100,200,user32=u)
    assert overlay.attached
    assert not (u.style & WS_CHILD)
    assert (u.style & WS_POPUP)
    assert ('place',100,100,800,300,600,480,0x10|0x40|0x04) in u.calls
    assert not any(op[0]=='parent' for op in u.calls)
    assert u.visible


def test_overlay_follows_launch_move_without_reparent():
    u=FakeWin32()
    overlay=ObsidianImeOverlay(100,200,user32=u)
    u.host_rect = (400,130,750,700)
    overlay.sync()
    assert any(op[:7]==('place',100,100,400,130,750,700) for op in u.calls)


def test_other_desktop_app_stays_above_overlay_without_hiding_it():
    u=FakeWin32()
    overlay=ObsidianImeOverlay(100,200,user32=u)
    u.front = 888
    u.foreground_pid = 444
    overlay.sync()
    assert u.visible is True
    assert any(call[0] == 'place' and call[2] == 888 for call in u.calls)
    assert not any(call[0]=='foreground' for call in u.calls)


def test_minimizing_launch_hides_overlay():
    u=FakeWin32()
    overlay=ObsidianImeOverlay(100,200,user32=u)
    u.iconic = True
    overlay.sync()
    assert not u.visible


def test_detach_restores_original_style_and_position_without_window_close():
    u=FakeWin32()
    original=(u.style,u.exstyle)
    overlay=ObsidianImeOverlay(100,200,user32=u)
    overlay.detach(foreground=False,show_window=False)
    assert not overlay.attached
    assert (u.style,u.exstyle)==original
    assert any(op[:7]==('place',100,-2,100,100,900,700) for op in u.calls)
    assert u.visible is False
    assert not any(op[0]=='foreground' for op in u.calls)


def test_only_obsidian_uses_overlay_other_apps_still_use_win32_child_host():
    source=(ROOT/'src'/'studio_preview_panel.py').read_text(encoding='utf-8')
    assert source.count('if overlay_enabled() else') == 2
    assert "if target.app == 'obsidian':" in source
    assert 'AttachedStudioWindow(hwnd, int(self.host.winId()))' in source
    assert 'self._sync_obsidian_ime_overlay' in source
