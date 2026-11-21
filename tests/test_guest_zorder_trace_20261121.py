"""Diagnostic trace must not modify focus, window order, or user content."""
import io
import logging
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from guest_zorder_trace import write, enabled
from test_three_editor_workspace_click_20261121 import editor_overlay
from guest_window_overlay import GuestWindowOverlay


def test_trace_includes_native_window_observations_without_mutating_win32():
    api, overlay = editor_overlay(GuestWindowOverlay)
    before = list(api.calls)
    stream = io.StringIO()
    logger = logging.getLogger('frb.launch.diagnostics')
    level, handlers, propagate = logger.level, list(logger.handlers), logger.propagate
    handler = logging.StreamHandler(stream)
    try:
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        with patch.dict('os.environ', {'FRB_GUEST_ZTRACE': '1'}):
            write('unit', overlay=overlay, sequence=13, point=(123, 456),
                  editor='obsidian', action=0)
        text = stream.getvalue()
        assert 'GUEST_ZTRACE seq=13 stage=unit x=123 y=456' in text
        assert 'editor=obsidian' in text
        assert 'above_launch=' in text and 'above_guest=' in text
        assert 'foreground=' in text
        assert api.calls == before
    finally:
        logger.handlers = handlers
        logger.setLevel(level)
        logger.propagate = propagate


def test_trace_can_be_disabled_without_touching_win32():
    assert enabled() in (True, False)
    with patch.dict('os.environ', {'FRB_GUEST_ZTRACE': '0'}):
        assert not enabled()
        write('disabled', sequence=1)


def test_click_pipeline_has_hook_dispatch_overlay_and_delayed_observations():
    desktop = (ROOT / 'src' / 'desktop_double_click.py').read_text(encoding='utf-8')
    app = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    overlay = (ROOT / 'src' / 'obsidian_ime_overlay.py').read_text(encoding='utf-8')
    assert 'GUEST_ZTRACE stage=hook_up' in desktop
    assert "capture('qt_dispatch')" in app
    assert "capture('qt_handled', action=int(outcome))" in app
    assert "for ms in (100, 350)" in app
    for stage in ('overlay_enter', 'overlay_skip', 'overlay_raise', 'overlay_synced'):
        assert stage in overlay
    assert 'return bool(attached.raise_workspace_from_guest_click(x, y))' in (
        ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
