"""Launcher child popup precedence over independent Obsidian overlay.

Win32 GDI is mocked. Final pixel compositing/IME must be checked on Windows.
"""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from guest_popup_occlusion import popup_cutouts, NativePopupMask, RGN_DIFF
from obsidian_ime_overlay import ObsidianImeOverlay


def test_clips_only_the_overlapped_popup_area_not_the_whole_guest():
    # Guest 100% is the host (800x600 device px), but Qt host uses 400x300 DIP.
    # A popup begins 50 DIP to the left and overlaps 250 DIP of the host.
    cuts = popup_cutouts((800,600), (400,300), [(-50,-10,300,150)])
    assert cuts == ((0,0,502,282),)
    assert popup_cutouts((800,600), (400,300), [(-120,15,100,100)]) == ()
    assert popup_cutouts((800,600), (400,300), []) == ()


def test_multiple_popups_are_merged_stably_deduplicated():
    rects=[(100,10,150,160),(0,50,40,80),(100,10,150,160)]
    cuts=popup_cutouts((400,300),(400,300),rects)
    assert cuts == ((0,48,42,132),(98,8,252,172))
    assert popup_cutouts((0,300),(400,300),rects) == ()
    assert popup_cutouts((400,300),(400,300),[(0,0,0,10),(10,10,-5,3)]) == ()


class FakeGDI:
    def __init__(self):
        self.next_handle=1
        self.regions={}
        self.deleted=[]
        self.combined=[]

    def CreateRectRgn(self,l,t,r,b):
        handle=self.next_handle; self.next_handle+=1
        self.regions[handle]=(l,t,r,b)
        return handle

    def CombineRgn(self,dst,src,hole,mode):
        assert mode==RGN_DIFF
        self.combined.append((dst,src,self.regions[hole],mode))
        return 3

    def DeleteObject(self,handle):
        self.deleted.append(handle)
        return True


class FakeUser32:
    def __init__(self):
        self.region_calls=[]
        self.region_enabled=False
        self.fail=False

    def SetWindowRgn(self,hwnd,region,redraw):
        self.region_calls.append((hwnd,region,redraw))
        if self.fail:return 0
        self.region_enabled=bool(region)
        return 1


def test_region_is_cut_without_hiding_guest_and_restored_when_popup_closes():
    u=FakeUser32();g=FakeGDI();mask=NativePopupMask(u,123,gdi32=g)
    cuts=popup_cutouts((400,200),(400,200),[(35,-10,300,150)])
    assert mask.apply((400,200),cuts)
    assert u.region_enabled
    assert len(g.combined)==1
    assert len(u.region_calls)==1
    assert u.region_calls[-1][2] is True
    assert mask.apply((400,200),cuts) # idle polling changes NOTHING
    assert len(u.region_calls)==1
    assert mask.apply((400,200),())
    assert u.region_calls[-1] == (123,0,True)
    assert not u.region_enabled
    assert mask.apply((400,200),())
    assert len(u.region_calls)==2
    assert len(g.deleted)==1 # only temporary hole, not handed-off region


def test_region_is_recalculated_after_resize_and_keeps_owners_correct():
    u=FakeUser32();g=FakeGDI();mask=NativePopupMask(u,123,gdi32=g)
    assert mask.apply((400,200),((0,0,100,50),))
    assert mask.apply((500,300),((0,0,120,50),))
    assert len(u.region_calls)==2
    assert len(g.deleted)==2 # temporary cutouts only
    # New region is owned by Windows; never DeleteObject a region transferred.
    assert u.region_calls[0][1] not in g.deleted
    assert u.region_calls[1][1] not in g.deleted


def test_region_is_not_replaced_on_win32_failure():
    u=FakeUser32();g=FakeGDI();mask=NativePopupMask(u,123,gdi32=g)
    u.fail=True
    assert not mask.apply((400,200),((0,0,100,50),))
    assert len(g.deleted)==2 # unsent base and temporary cutout
    u.fail=False
    assert mask.apply((400,200),((0,0,100,50),))
    assert mask.clear()


def test_panel_passes_native_history_hwnds_not_region_masks():
    # The old mask caused a white guest window to cover Launcher popups.
    # Native owned Qt.Tool windows now have their own HWNDs, and the guest
    # is placed just beneath the popup without touching the IME context.
    source=(ROOT/'src/studio_preview_panel.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StudioPreviewPanel')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_launcher_popup_hwnds')
    code=ast.get_source_segment(source,method)
    assert "getattr(launch, 'history_popup', None)" in code
    assert "getattr(exp, 'favorite_popup', None)" in code
    assert 'popup.isVisible() and popup.isWindow()' in code
    assert 'popup_hwnds=self._launcher_popup_hwnds()' in source
    overlay=(ROOT/'src/obsidian_ime_overlay.py').read_text(encoding='utf-8')
    assert 'self._popup_mask.clear()' in overlay
    assert 'self._popup_mask.apply((rect[2], rect[3]), cuts)' not in overlay
    assert 'after = (self.hwnd if already_above else (popup or above))' in overlay



def test_both_history_panels_update_guest_stacking_immediately():
    app=(ROOT/'src/app.py').read_text(encoding='utf-8')
    view=(ROOT/'src/expanded_view.py').read_text(encoding='utf-8')
    def method_source(source,class_name,method_name):
        top=ast.parse(source)
        klass=next(n for n in top.body if isinstance(n,ast.ClassDef) and n.name==class_name)
        method=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name==method_name)
        return ast.get_source_segment(source,method)
    for name in ('show_history_popup','hide_history_popup'):
        part=method_source(app,'Launcher',name)
        assert 'self.expanded_view.refresh_guest_popup_priority()' in part
    for name in ('toggle_directory_favorites','hide_favorite_popup'):
        part=method_source(view,'ExpandedLauncherView',name)
        assert 'self.refresh_guest_popup_priority()' in part
