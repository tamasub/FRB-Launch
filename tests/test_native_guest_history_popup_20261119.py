"""Native Launcher-owned history windows outrank a non-parented Obsidian guest.

Structural and fake-Win32 tests. The actual Windows/Qt composition + focus
transfer must be verified interactively; PySide6 is not available on Linux.
"""
from pathlib import Path
import ast
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from test_guest_overlay_zorder_and_popout_20261119 import (
    Desktop, ObsidianImeOverlay, GUEST, HOST, LAUNCH, CHROME, WS_EX_TOPMOST,
)

APP = (ROOT / 'src/app.py').read_text(encoding='utf-8')
EXP = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
PANEL = (ROOT / 'src/studio_preview_panel.py').read_text(encoding='utf-8')
OVERLAY = (ROOT / 'src/obsidian_ime_overlay.py').read_text(encoding='utf-8')


def method(source, cls, name):
    tree = ast.parse(source)
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in klass.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def source_of(source, cls, name):
    return ast.get_source_segment(source, method(source, cls, name))


def test_search_history_is_owned_native_tool_not_a_grabbing_qt_popup():
    code=source_of(APP,'Launcher','__init__')
    assert 'self.history_popup = QFrame(' in code
    assert 'self, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint' in code
    assert 'Qt.WidgetAttribute.WA_ShowWithoutActivating, True' in code
    assert 'self.history_filter = QLineEdit(self.history_popup)' in code
    show=source_of(APP,'Launcher','show_history_popup')
    assert 'self.history_popup.show()' in show
    assert 'self.search.setFocus(' in show
    assert 'self.expanded_view.refresh_guest_popup_priority()' in show


def test_breadcrumb_history_is_owned_native_tool_with_original_focus_routing():
    code=source_of(EXP, 'ExpandedLauncherView', '__init__')
    assert 'self.favorite_popup = QFrame(' in code
    assert 'self.launcher, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint' in code
    assert 'Qt.WidgetAttribute.WA_ShowWithoutActivating, True' in code
    open_code=source_of(EXP, 'ExpandedLauncherView', 'toggle_directory_favorites')
    assert 'self.favorite_dropdown.setFocus(' in open_code
    assert 'self.favorite_popup.show()' in open_code
    assert 'self.refresh_guest_popup_priority()' in open_code


def test_both_popups_use_global_geometry_but_keep_launcher_relative_anchor_math():
    main=source_of(APP,'Launcher','position_history_popup')
    breadcrumb=source_of(EXP,'ExpandedLauncherView','position_directory_favorites')
    assert 'self.mapToGlobal(QPoint(x, y))' in main
    assert 'self.history_popup.setGeometry(origin.x(), origin.y(), width, height)' in main
    assert 'self.launcher.mapToGlobal(QPoint(x, y))' in breadcrumb
    assert 'self.favorite_popup.setGeometry(origin.x(), origin.y(), width, height)' in breadcrumb
    assert 'popup_tree_height(' in main and 'popup_tree_height(' in breadcrumb


def test_application_becoming_inactive_dismisses_both_histories():
    code=source_of(APP,'Launcher','_dismiss_histories_when_inactive')
    scope={'Qt': NS(ApplicationState=NS(ApplicationActive=1))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method(APP,'Launcher','_dismiss_histories_when_inactive')],type_ignores=[])),'app.py','exec'),scope)
    func=scope['_dismiss_histories_when_inactive']
    history=NS(isVisible=lambda:True)
    favorite=NS(isVisible=lambda:True)
    obj=NS(history_popup=history,expanded_view=NS(favorite_popup=favorite),hide_history_popup=Mock())
    obj.expanded_view.hide_favorite_popup=Mock()
    func(obj,1)
    obj.hide_history_popup.assert_not_called()
    func(obj,2)
    obj.hide_history_popup.assert_called_once_with()
    obj.expanded_view.hide_favorite_popup.assert_called_once_with()


def test_overlay_receives_native_popup_hwnds_not_mask_rectangles():
    code=source_of(PANEL,'StudioPreviewPanel','_launcher_popup_hwnds')
    assert 'popup.isVisible() and popup.isWindow()' in code
    assert 'popup.winId()' in code
    sync=source_of(PANEL,'StudioPreviewPanel','_sync_obsidian_ime_overlay')
    assert 'popup_hwnds=self._launcher_popup_hwnds()' in sync
    assert 'popup_rects=self._launcher_popup_rects()' not in sync
    assert 'self.u.SetParent(' not in OVERLAY


def test_popup_promoted_in_front_of_guest_without_hiding_or_cutting():
    POPUP=900
    class WithPopup(Desktop):
        def IsWindow(self,hwnd): return hwnd == POPUP or super().IsWindow(hwnd)
    u=WithPopup(); overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    assert u.stack.index(CHROME)<u.stack.index(GUEST)<u.stack.index(LAUNCH)
    # Qt native Tool popup appears directly in front of Launch; at this
    # moment the external guest is above it and covers the menu.
    u.stack.remove(GUEST)
    u.stack.insert(u.stack.index(LAUNCH), POPUP)
    u.stack.insert(u.stack.index(POPUP), GUEST)
    u.exstyles[POPUP]=0
    prior=len(u.calls)
    overlay.sync(popup_hwnds=(POPUP,))
    assert u.stack.index(CHROME)<u.stack.index(POPUP)<u.stack.index(GUEST)<u.stack.index(LAUNCH)
    assert u.visible
    assert not any(x[0]=='show' and x[1]==0 for x in u.calls[prior:])
    assert all(x[0]!='foreground' for x in u.calls)
    assert overlay._popup_mask._key is None  # absolutely no SetWindowRgn holes


def test_temporary_popup_does_not_keep_guest_topmost_after_close():
    POPUP=900
    class WithPopup(Desktop):
        def IsWindow(self,hwnd): return hwnd == POPUP or super().IsWindow(hwnd)
    u=WithPopup(); overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    u.stack.insert(0,POPUP)
    u.exstyles[POPUP]=0
    overlay.sync(popup_hwnds=(POPUP,))
    u.stack.remove(POPUP)
    overlay.sync(popup_hwnds=())
    assert u.stack.index(CHROME)<u.stack.index(GUEST)<u.stack.index(LAUNCH)
    assert not u.exstyles[GUEST]&WS_EX_TOPMOST
    assert u.visible


def test_topmost_popup_does_not_promote_normal_guest_to_topmost():
    POPUP=900
    class WithPopup(Desktop):
        def IsWindow(self,hwnd): return hwnd == POPUP or super().IsWindow(hwnd)
    u=WithPopup();overlay=ObsidianImeOverlay(GUEST,HOST,user32=u)
    u.stack.insert(0,POPUP)
    u.exstyles[POPUP]=WS_EX_TOPMOST
    overlay.sync(popup_hwnds=(POPUP,))
    assert not (u.exstyles[GUEST]&WS_EX_TOPMOST)
    assert u.stack.index(POPUP)<u.stack.index(GUEST)<u.stack.index(LAUNCH)


def test_launch_drag_repositions_native_popups():
    drag=source_of(APP,'Launcher','moveEvent')
    assert 'self.position_history_popup()' in drag
    assert 'expanded.position_directory_favorites()' in drag
