"""Read-only, time-bounded Obsidian pop-out instrumentation (Qt-free tests)."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import obsidian_popout_activation_trace as trace


def test_trace_has_no_events_until_popout_and_uses_private_rotating_jsonl(tmp_path, monkeypatch):
    trace.reset_for_test()
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    trace.record('launch_mouse_press_delivered')
    trace.poll()
    assert not trace.trace_path().exists()
    monkeypatch.setattr(trace, '_native_snapshot', lambda launch, obs: {
        'foreground': obs, 'foreground_role': 'obsidian', 'obsidian_above_launch': True,
        'launch': {'topmost': False}, 'obsidian': {'topmost': False, 'parent': 0, 'owner': 0}})
    assert trace.begin(400, 200, route='third_column_x')
    trace.record('notopmost_release', success=True)
    trace.poll()
    data = [json.loads(x) for x in trace.trace_path().read_text(encoding='utf-8').splitlines()]
    assert [x['event'] for x in data] == [
        'detach_before', 'notopmost_release', 'window_state_changed']
    assert data[-1]['foreground_role'] == 'obsidian'
    assert data[-2]['success'] is True
    assert 'FRBLaunch' in str(trace.trace_path())
    trace.reset_for_test()


def test_poll_records_zorder_or_foreground_transition_and_times_out(tmp_path, monkeypatch):
    trace.reset_for_test()
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    state = {'fg': 400, 'above': True}
    monkeypatch.setattr(trace, '_native_snapshot', lambda launch, obs: {
        'foreground': state['fg'], 'obsidian_above_launch': state['above'],
        'launch': {'topmost': False}, 'obsidian': {'topmost': False, 'parent': 0, 'owner': 0}})
    assert trace.begin(400, 200, route='pop_out_button')
    trace.poll()
    lines = trace.trace_path().read_text(encoding='utf-8').splitlines()
    trace.poll()  # No change, no extra log on every 160ms timer.
    assert len(trace.trace_path().read_text(encoding='utf-8').splitlines()) == len(lines)
    state['fg'] = 200
    state['above'] = False
    trace.poll()
    events = [json.loads(x) for x in trace.trace_path().read_text(encoding='utf-8').splitlines()]
    assert events[-1]['event'] == 'window_state_changed'
    assert events[-1]['foreground'] == 200
    assert events[-1]['obsidian_above_launch'] is False
    trace._SESSION['started'] -= trace.TRACE_SECONDS + 1
    trace.poll()
    assert not trace.active()
    events = [json.loads(x) for x in trace.trace_path().read_text(encoding='utf-8').splitlines()]
    assert events[-1]['event'] == 'trace_end'


def test_invalid_window_handle_does_not_start_trace(monkeypatch, tmp_path):
    trace.reset_for_test()
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    assert not trace.begin(0, 200, route='third_column_x')
    assert not trace.active()
    assert not trace.trace_path().exists()


def test_instrumentation_covers_both_obisdian_release_routes():
    src = (ROOT / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    panel = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                 and n.name == 'StudioPreviewPanel')
    methods = {n.name: ast.get_source_segment(src, n)
               for n in panel.body if isinstance(n, ast.FunctionDef)}
    assert "'pop_out_button'" in methods['pop_out_obsidian']
    assert "'third_column_x'" in methods['close_external_editors']
    assert "'_begin_obsidian_desktop_trace'" in methods['pop_out_obsidian']
    assert "'_begin_obsidian_desktop_trace'" in methods['close_external_editors']
    for name in ('pop_out_obsidian', 'close_external_editors'):
        assert "'detach_after'" in methods[name]
        assert "'notopmost_release'" in methods[name]
        assert "'_schedule_obsidian_desktop_trace'" in methods[name]
    assert 'QTimer.singleShot' in methods['_schedule_obsidian_desktop_trace']
    assert 'poll_obsidian_desktop()' in methods['_sync_obsidian_ime_overlay']


def test_launch_click_trace_is_before_foreground_repair_and_never_eats_click():
    src = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    node = ast.parse(src)
    klass = next(n for n in node.body if isinstance(n, ast.ClassDef)
                 and n.name == 'NormalWindowClickActivationFilter')
    fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
              and n.name == 'eventFilter')
    source = ast.get_source_segment(src, fn)
    assert source.index("'launch_mouse_press_delivered'") < source.index('launcher.restore_keyboard_focus(')
    assert "'launch_click_delayed'" in source
    assert source.rstrip().endswith('return False')


def test_normal_launch_click_has_readonly_trace_and_keeps_original_repair(monkeypatch):
    from unittest.mock import Mock
    src = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    node = ast.parse(src)
    klass = next(n for n in node.body if isinstance(n, ast.ClassDef)
                 and n.name == 'NormalWindowClickActivationFilter')
    fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
              and n.name == 'eventFilter')
    namespace = {}
    calls, tasks = [], []
    monkeypatch.setattr(trace, 'record', lambda event, **kw: calls.append((event, kw)))
    monkeypatch.setattr(trace, 'active', lambda: True)
    class Widget:
        def __init__(self, win): self.win = win
        def window(self): return self.win
    launcher = SimpleNamespace(dismiss_on_outside_click=False,
                               isVisible=lambda: True, isMinimized=lambda: False,
                               winId=lambda: 303, restore_keyboard_focus=Mock())
    namespace.update(QEvent=SimpleNamespace(Type=SimpleNamespace(MouseButtonPress='mouse')),
                     QWidget=Widget, qt_object_is_valid=lambda o: True,
                     windows=SimpleNamespace(foreground=lambda: 404,
                                             raise_normal_window=lambda h: True),
                     QTimer=SimpleNamespace(singleShot=lambda ms, cb: tasks.append((ms, cb))),
                     DIAG=SimpleNamespace(info=lambda *args: None))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 'app.py', 'exec'), namespace)
    result = namespace['eventFilter'](SimpleNamespace(launcher=launcher),
                                      Widget(launcher),
                                      SimpleNamespace(type=lambda: 'mouse'))
    assert result is False
    assert calls[0][0] == 'launch_mouse_press_delivered'
    assert launcher.restore_keyboard_focus.call_count == 0
    for _, callback in tasks:
        callback()
    assert launcher.restore_keyboard_focus.call_count == 1
    assert any(event == 'launch_activation_repair_result' and kw['raised'] is True
               for event, kw in calls)
