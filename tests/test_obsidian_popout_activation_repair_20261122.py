"""Focused Windows activation repair tests: no native desktop required."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from studio_win32_host import activate_obsidian_desktop_after_release
import obsidian_popout_activation_trace as trace


class FakeUser:
    def __init__(self, foreground=100):
        self.fg = foreground
        self.calls = []
        self.allow = True
        self.valid = {100, 200}

    def IsWindow(self, hwnd):
        return hwnd in self.valid

    def GetParent(self, hwnd):
        return getattr(self, 'parent', 0)

    def GetForegroundWindow(self):
        return self.fg

    def SetForegroundWindow(self, hwnd):
        self.calls.append(hwnd)
        if self.allow:
            self.fg = hwnd
        return self.allow


def test_handoff_activates_detached_obsidian_if_launch_is_foreground():
    u = FakeUser(100)
    assert activate_obsidian_desktop_after_release(200, 100, user32=u)
    assert u.calls == [200] and u.fg == 200
    assert activate_obsidian_desktop_after_release(200, 100, user32=u)
    assert u.calls == [200], 'Do not repeatedly activate already foreground guest'


def test_handoff_never_steals_other_foreground_and_checks_valid_hwnd():
    u = FakeUser(300)
    assert not activate_obsidian_desktop_after_release(200, 100, user32=u)
    assert not u.calls
    u.fg = 100
    assert not activate_obsidian_desktop_after_release(200, 0, user32=u)
    assert not activate_obsidian_desktop_after_release(999, 100, user32=u)
    assert not u.calls
    u.parent = 999  # The window has already been re-docked.
    assert not activate_obsidian_desktop_after_release(200, 100, user32=u)
    assert not u.calls
    u.parent = 0
    u.allow = False
    assert not activate_obsidian_desktop_after_release(200, 100, user32=u)
    assert u.calls == [200]


def test_stale_zorder_repair_requires_specific_detached_active_launch(monkeypatch):
    trace.reset_for_test()
    snapshot = {'foreground': 100, 'obsidian_above_launch': True,
                'launch': {'valid': True, 'topmost': False},
                'obsidian': {'valid': True, 'topmost': False, 'parent': 0}}
    monkeypatch.setattr(trace, '_native_snapshot', lambda *_: snapshot)
    monkeypatch.setattr(trace, 'record', lambda *a, **k: None)
    assert trace.begin(200, 100, route='third_column_x')
    assert trace.launch_click_needs_zorder_repair(100)
    assert not trace.launch_click_needs_zorder_repair(101)
    for field, value in [('foreground', 200), ('obsidian_above_launch', False)]:
        original = snapshot[field]
        snapshot[field] = value
        assert not trace.launch_click_needs_zorder_repair(100)
        snapshot[field] = original
    snapshot['obsidian']['parent'] = 555
    assert not trace.launch_click_needs_zorder_repair(100)
    snapshot['obsidian']['parent'] = 0
    snapshot['obsidian']['topmost'] = True
    assert not trace.launch_click_needs_zorder_repair(100)
    trace.reset_for_test()
    assert not trace.launch_click_needs_zorder_repair(100)


def extracted_class_method(source_file, klass, method, globals):
    source = ast.parse((ROOT / 'src' / source_file).read_text(encoding='utf-8'))
    node = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == klass)
    fun = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == method)
    ns = dict(globals)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fun], type_ignores=[])),
                 source_file, 'exec'), ns)
    return ns[method]


def test_first_launch_click_repairs_stale_zorder_even_if_already_foreground(monkeypatch):
    # This is the exact failure observed in the real user's native trace.
    calls, queue = [], []
    monkeypatch.setattr(trace, 'active', lambda: True)
    monkeypatch.setattr(trace, 'record', lambda event, **kw: calls.append((event, kw)))
    stale = {'value': True}
    monkeypatch.setattr(trace, 'launch_click_needs_zorder_repair', lambda hwnd: stale['value'])
    class Widget:
        def window(self): return launcher
    launcher = NS(dismiss_on_outside_click=False, isVisible=lambda: True,
                  isMinimized=lambda: False, winId=lambda: 100,
                  restore_keyboard_focus=Mock())
    raised = []
    method = extracted_class_method('app.py', 'NormalWindowClickActivationFilter',
        'eventFilter', {
            'QEvent': NS(Type=NS(MouseButtonPress='mouse')),
            'QWidget': Widget, 'qt_object_is_valid': lambda x: True,
            'windows': NS(foreground=lambda: 100,
                          raise_normal_window=lambda hwnd: raised.append(hwnd) or True),
            'QTimer': NS(singleShot=lambda ms, cb: queue.append(cb)),
            'DIAG': NS(info=lambda *a: None),
        })
    event = NS(type=lambda: 'mouse')
    assert method(NS(launcher=launcher), Widget(), event) is False
    assert len(queue) == 4  # Three trace snapshots and one guarded repair.
    for callback in queue:
        callback()
    assert raised == [100]
    assert launcher.restore_keyboard_focus.call_count == 0
    assert any(ev == 'launch_activation_repair_result' and
               kw.get('obsidian_stale') for ev, kw in calls)
    # Without the specific mismatch, no activation repair is scheduled.
    raised.clear(); queue.clear(); stale['value'] = False
    assert method(NS(launcher=launcher), Widget(), event) is False
    for callback in queue:
        callback()
    assert not raised


def test_stale_zorder_must_still_exist_at_deferred_repair(monkeypatch):
    calls, queue = [], []
    monkeypatch.setattr(trace, 'active', lambda: True)
    monkeypatch.setattr(trace, 'record', lambda *a, **kw: None)
    stale = {'value': True}
    monkeypatch.setattr(trace, 'launch_click_needs_zorder_repair', lambda hwnd: stale['value'])
    class Widget:
        def window(self): return launcher
    launcher = NS(dismiss_on_outside_click=False, isVisible=lambda: True,
                  isMinimized=lambda: False, winId=lambda: 100,
                  restore_keyboard_focus=Mock())
    method = extracted_class_method('app.py', 'NormalWindowClickActivationFilter',
        'eventFilter', {
            'QEvent': NS(Type=NS(MouseButtonPress='mouse')),
            'QWidget': Widget, 'qt_object_is_valid': lambda x: True,
            'windows': NS(foreground=lambda: 100,
                          raise_normal_window=lambda hwnd: calls.append(hwnd) or True),
            'QTimer': NS(singleShot=lambda ms, cb: queue.append(cb)),
            'DIAG': NS(info=lambda *a: None),
        })
    method(NS(launcher=launcher), Widget(), NS(type=lambda: 'mouse'))
    stale['value'] = False
    for callback in queue: callback()
    assert not calls


def test_popout_activation_callback_is_post_close_and_obsidian_only():
    src = (ROOT / 'src/studio_preview_panel.py').read_text(encoding='utf-8')
    pop = src.split('    def pop_out_obsidian(self):', 1)[1].split('    def pop_out_studio(self):', 1)[0]
    close = src.split('    def close_external_editors(self):', 1)[1].split('    def external_embedding_pending(self):', 1)[0]
    assert pop.index('self.popout_requested.emit()') < pop.index('self._schedule_obsidian_desktop_activation')
    assert close.index('attached.detach(') < close.index('self._schedule_obsidian_desktop_activation(')
    assert 'if detached_obsidian is not None:' in close
    schedule = extracted_class_method('studio_preview_panel.py', 'StudioPreviewPanel',
        '_schedule_obsidian_desktop_activation', {'QTimer': NS(singleShot=lambda ms, cb: queue.append((ms, cb)))})
    queue = []
    fake = NS(window=lambda: NS(winId=lambda: 100))
    schedule(fake, 200, FakeUser(100))
    assert len(queue) == 1 and queue[0][0] == 0
    queue[0][1]()  # The deferred callback actually performs the handoff.
