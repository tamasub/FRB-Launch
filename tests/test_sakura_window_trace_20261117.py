"""Sakura detection tracing must be observational, bounded and UTF-8 safe."""
import json
import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_trace_in_localappdata_no_settings_written(tmp_path, monkeypatch):
    from sakura_window_trace import trace
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    trace('CONSENT_PATH_REACHED', hwnd=42, title='あいう.txt - サクラエディタ', pid=123)
    p = tmp_path / 'FRBLaunch' / 'sakura_window_trace.log'
    assert p.exists()
    record = json.loads(p.read_text(encoding='utf-8').strip())
    assert record['title'] == 'あいう.txt - サクラエディタ'
    assert record['hwnd'] == 42 and record['pid'] == 123
    assert not (tmp_path / 'FRBLaunch' / 'state.ini').exists()


def test_log_failure_never_blocks_launch(monkeypatch, tmp_path):
    from sakura_window_trace import trace
    # A file where a directory is needed provokes a write error.
    bad = tmp_path / 'not_a_directory'
    bad.write_text('x')
    monkeypatch.setenv('LOCALAPPDATA', str(bad))
    assert trace('OPEN_BEGIN', file='test.txt') is None


def test_rotation_keeps_one_prior_trace(monkeypatch, tmp_path):
    import sakura_window_trace as t
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(t, 'MAX_BYTES', 20)
    t.trace('FIRST')
    t.trace('SECOND')
    assert (tmp_path / 'FRBLaunch' / (t.LOG_NAME + '.old')).exists()
    current = (tmp_path / 'FRBLaunch' / t.LOG_NAME).read_text(encoding='utf-8')
    assert 'SECOND' in current


def test_non_windows_raw_snapshot_does_not_raise(tmp_path, monkeypatch):
    import sakura_window_trace as t
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    if os.name != 'nt':
        t.trace_windows('test_scan')
        line = (tmp_path / 'FRBLaunch' / t.LOG_NAME).read_text(encoding='utf-8')
        assert 'WINDOW_SCAN_UNSUPPORTED' in line


def test_source_has_route_scan_and_prompt_result():
    panel = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
    view = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    assert "'ROUTE_FROM_FILES_LIST'" in view
    assert "'OPEN_BEGIN'" in panel
    assert "'WINDOW_SCAN'" in (SRC / 'sakura_window_trace.py').read_text(encoding='utf-8')
    assert "'EXISTING_SELECTION'" in panel
    assert "'CONSENT_DIALOG_CALL'" in panel
    assert "'CONSENT_DIALOG_RESULT'" in panel
    assert "'POLL_TIMEOUT'" in panel
