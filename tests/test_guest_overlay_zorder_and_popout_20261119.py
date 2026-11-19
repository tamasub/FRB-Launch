"""FRB Guest Overlay: foreground order + explicit outside controls.

Mock Win32 on non-Windows; not a substitute for Windows GUI verification.
"""
import ast
import sys
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from obsidian_ime_overlay import (ObsidianImeOverlay, SWP_NOACTIVATE,
                                  SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER,
                                  SWP_SHOWWINDOW, WS_EX_TOPMOST)
from studio_win32_host import WS_POPUP, GWL_STYLE, GWL_EXSTYLE

GUEST, HOST, LAUNCH, CHROME, VSCODE = 100, 200, 300, 400, 500


class F:
    def __init__(self, fn): self.fn = fn
    def __call__(self, *args): return self.fn(*args)


class Desktop:
    def __init__(self):
        # Top->bottom, both app windows are normal-tier peers.
        self.stack = [CHROME, VSCODE, LAUNCH, GUEST]
        self.foreground = CHROME
        self.iconic = False
        self.rect = (1000, 250, 700, 500)
        self.styles = {GUEST:WS_POPUP|0x10000000|0x00C00000}
        self.exstyles = {GUEST:0x00040000, LAUNCH:0}
        self.visible = True
        self.calls = []
        self.GetClientRect = F(self.client_rect)
        self.ClientToScreen = F(self.to_screen)
        self.IsIconic = F(lambda hwnd:self.iconic)
        self.GetWindow = F(self.get_window)

    def IsWindow(self, hwnd): return hwnd in (GUEST, HOST, LAUNCH, CHROME, VSCODE)
    def GetWindowLongPtrW(self, hwnd, index):
        return self.styles.get(hwnd,0) if index == GWL_STYLE else self.exstyles.get(hwnd,0)
    def SetWindowLongPtrW(self, hwnd, index, value):
        (self.styles if index==GWL_STYLE else self.exstyles)[hwnd] = value
        return 1
    def GetWindowRect(self, hwnd, ptr):
        r=ptr._obj; r.left=10;r.top=20;r.right=700;r.bottom=520
        return True
    def GetAncestor(self, hwnd, kind):return LAUNCH
    def GetForegroundWindow(self): return self.foreground
    def get_window(self, hwnd, cmd):
        assert cmd==3
        index=self.stack.index(hwnd)
        return 0 if index==0 else self.stack[index-1]
    def client_rect(self, hwnd, ptr):
        r=ptr._obj;r.left=0;r.top=0;r.right=self.rect[2];r.bottom=self.rect[3]
        return True
    def to_screen(self, hwnd, ptr):
        ptr._obj.x=self.rect[0];ptr._obj.y=self.rect[1]
        return True
    def ShowWindow(self, hwnd, operation):
        self.calls.append(('show',operation))
        self.visible=operation!=0
        return True
    def SetWindowPos(self, hwnd, after,x,y,w,h, flags):
        self.calls.append(('place',hwnd,after,x,y,w,h,flags))
        # Simulate changes to the Z order for HWND_TOP, NOTOPMOST or HWNDs.
        if not (flags & SWP_NOZORDER):
            self.stack.remove(hwnd)
            if after in (0,-1,-2):
                self.stack.insert(0,hwnd)
                if after==-1: self.exstyles[hwnd]=self.exstyles.get(hwnd,0)|WS_EX_TOPMOST
                if after==-2: self.exstyles[hwnd]=self.exstyles.get(hwnd,0)&~WS_EX_TOPMOST
            else:
                self.stack.insert(self.stack.index(after)+1,hwnd)
        if flags & SWP_SHOWWINDOW: self.visible=True
        return True
    def SetForegroundWindow(self,hwnd):
        self.calls.append(('foreground',hwnd))
        self.foreground=hwnd
        return True


def test_chrome_selected_has_priority_and_guest_stays_visible_below_chrome():
    u=Desktop()
    overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    assert u.foreground==CHROME
    assert u.visible
    assert u.stack.index(CHROME)<u.stack.index(GUEST)<u.stack.index(LAUNCH)
    assert not (u.exstyles[GUEST] & WS_EX_TOPMOST)
    assert not any(c[0]=='foreground' for c in u.calls)
    initial=len(u.calls)
    for _ in range(8): overlay.sync()
    assert len(u.calls)==initial, 'Idle polling must not raise or flicker windows'


def test_chrome_and_vscode_can_each_occlude_guest_without_hiding_it():
    u=Desktop();overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    u.stack.remove(VSCODE);u.stack.insert(0,VSCODE);u.foreground=VSCODE
    overlay.sync()
    assert u.stack.index(VSCODE)<u.stack.index(GUEST)<u.stack.index(LAUNCH)
    assert u.visible
    assert u.foreground==VSCODE


def test_launch_selected_regains_guest_in_front_of_launch_not_focus():
    u=Desktop();overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    u.stack.remove(LAUNCH);u.stack.insert(0,LAUNCH);u.foreground=LAUNCH
    overlay.sync()
    assert u.stack.index(GUEST)<u.stack.index(LAUNCH)<u.stack.index(CHROME)
    assert u.foreground==LAUNCH  # do not force keyboard focus to Obsidian


def test_clicking_guest_brings_launch_group_forward_and_keeps_guest_foreground():
    u=Desktop();overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    u.stack.remove(GUEST);u.stack.insert(0,GUEST);u.foreground=GUEST
    overlay.sync()
    assert u.stack.index(GUEST)<u.stack.index(LAUNCH)<u.stack.index(CHROME)
    assert u.foreground==GUEST
    assert not any(c[0]=='foreground' for c in u.calls)


def test_minimized_launch_hides_overlay_but_never_kills_guest():
    u=Desktop();overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    u.iconic=True;overlay.sync()
    assert not u.visible
    u.iconic=False;overlay.sync()
    assert u.visible



def test_topmost_browser_never_promotes_normal_launch_guest_to_topmost():
    u=Desktop()
    u.exstyles[CHROME]=WS_EX_TOPMOST
    # Chrome is the only desktop window above Launch (normal tier).
    u.stack=[CHROME,LAUNCH,GUEST,VSCODE]
    overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    # HWND_TOP means top of *normal* tier on Windows, below TOPMOST Chrome.
    # The minimal mock does not model Windows tier boundaries; inspect API
    # instructions instead of inferring real stacking from this mock list.
    assert any(c[0]=='place' and c[1]==GUEST and c[2]==0 for c in u.calls)
    assert not (u.exstyles[GUEST] & WS_EX_TOPMOST)
    assert u.foreground==CHROME


def test_background_launch_position_change_follows_without_stealing_focus():
    u=Desktop();overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    u.rect=(260,190,550,700)
    overlay.sync()
    assert any(c[0]=='place' and c[1]==GUEST
               and c[3:7]==(260,190,550,700) for c in u.calls)
    assert u.foreground==CHROME


def test_browser_external_control_uses_existing_url_not_observer_process():
    b=(ROOT/'src/browser_preview_panel.py').read_text(encoding='utf-8')
    w=(ROOT/'src/launch_web_view.py').read_text(encoding='utf-8')
    assert 'self.web_view.external.hide()' in b
    assert 'return self.web_view.open_external()' in b
    assert 'QDesktopServices.openUrl(view.url())' in w


def method(name):
    tree=ast.parse((ROOT/'src/studio_preview_panel.py').read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StudioPreviewPanel')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
    scope={}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),name,'exec'),scope)
    return scope[name]


class PopoutButton:
    def __init__(self): self.visible=False;self.enabled=False;self.tooltip=''
    def setVisible(self,x):self.visible=x
    def setEnabled(self,x):self.enabled=x
    def setToolTip(self,x):self.tooltip=x


class FakeOverlay:
    def __init__(self): self.hwnd=111;self.attached=True;self.detached=[]
    def detach(self,**kwargs): self.detached.append(kwargs);self.attached=False


class FakeTimer:
    def __init__(self): self.stopped=False
    def stop(self):self.stopped=True


class FakeSignal:
    def __init__(self): self.emits=0
    def emit(self):self.emits+=1


def make_obsidian_panel():
    obj=SimpleNamespace(
        _external_key=('obsidian','a.md'),_external_pending=None,
        _attached=FakeOverlay(),_obsidian_cli_busy=None,
        _studio_popout_pending=False,_studio_dock_pending=False,
        _target=None,_process=None,_external_timer=FakeTimer(),
        _obsidian_main_probe_token='token',_obsidian_main_probe_busy=True,
        _reset_obsidian_cli=lambda:None,
        status_label=SimpleNamespace(setText=lambda x:None,show=lambda:None),
        popout_button=PopoutButton(),close_button=PopoutButton(),
        popout_requested=FakeSignal(),
    )
    obj.sakura_attached=lambda:False
    obj._sync_popout_button=lambda:method('_sync_popout_button')(obj)
    return obj


def test_obsidian_has_outside_button_and_does_not_close_on_popout():
    obj=make_obsidian_panel()
    obj._sync_popout_button()
    assert obj.popout_button.visible and obj.popout_button.enabled
    assert 'Obsidian' in obj.popout_button.tooltip
    assert method('pop_out_obsidian')(obj) is True
    assert obj._attached is None and obj._external_key is None
    assert obj._external_timer.stopped
    assert obj.popout_requested.emits==1


def test_obsidian_popout_waits_for_cli_operation():
    obj=make_obsidian_panel();obj._obsidian_cli_busy='switch'
    obj._sync_popout_button()
    assert obj.popout_button.visible and not obj.popout_button.enabled
    assert method('pop_out_obsidian')(obj) is False
    assert obj.popout_requested.emits==0


def test_browser_studio_obsidian_external_controls_are_aligned_before_close():
    b=(ROOT/'src/browser_preview_panel.py').read_text(encoding='utf-8')
    s=(ROOT/'src/studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'self.popout_button.clicked.connect(self.open_external)' in b
    assert 'return self.web_view.open_external()' in b
    assert b.index('bar.addWidget(self.maximize_button)')<b.index('bar.addWidget(self.popout_button)')<b.index('bar.addWidget(self.close_button)')
    assert s.index('bar.addWidget(self.maximize_button)')<s.index('bar.addWidget(self.popout_button)')<s.index('bar.addWidget(self.close_button)')
    assert 'return self.pop_out_obsidian()' in s
    assert "browser_navigation_icon('external', family)" in b
