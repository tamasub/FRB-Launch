"""Ensure native Sakura captions survive the top-level (no SetParent) path."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_sakura_overlay_class_exists_and_preserves_native_caption():
    from guest_window_overlay import SakuraGuestOverlay, GuestWindowOverlay
    from studio_win32_host import (WS_CHILD, WS_POPUP, WS_CAPTION, WS_SYSMENU,
                                   WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX)
    assert issubclass(SakuraGuestOverlay, GuestWindowOverlay)
    assert SakuraGuestOverlay.native_frame_on_attach is False
    assert SakuraGuestOverlay.preserve_native_styles is True
    sample = SakuraGuestOverlay.__new__(SakuraGuestOverlay)
    sample.original_style = (WS_CAPTION | WS_SYSMENU | WS_THICKFRAME |
                             WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
    style = sample._overlay_window_style()
    assert style == sample.original_style  # No WS_POPUP or style stripping
    assert not style & WS_CHILD


def test_others_keep_existing_chromium_frame_policy():
    from guest_window_overlay import GuestWindowOverlay
    from studio_win32_host import WS_CHILD, WS_POPUP, WS_CAPTION
    sample = GuestWindowOverlay.__new__(GuestWindowOverlay)
    sample.original_style = WS_CHILD | WS_CAPTION
    style = sample._overlay_window_style()
    assert style & WS_POPUP
    assert not style & WS_CHILD
    assert not style & WS_CAPTION
    assert GuestWindowOverlay.native_frame_on_attach is False


def test_sakura_open_and_switch_only_use_overlay_adapter():
    code = (ROOT / "src" / "studio_preview_panel.py").read_text(encoding="utf-8")
    tree = ast.parse(code)
    methods = {node.name: node for cls in tree.body if isinstance(cls, ast.ClassDef)
               for node in cls.body if isinstance(node, ast.FunctionDef)}
    for name in ("_open_sakura_guest", "_poll_sakura_guest"):
        method = methods[name]
        source = ast.get_source_segment(code, method)
        assert "SakuraGuestOverlay(" in source
        assert "AttachedStudioWindow(" not in source
        assert "SetParent(" not in source
    assert "self._poll_sakura_guest()" in ast.get_source_segment(code, methods["_poll_external"])
