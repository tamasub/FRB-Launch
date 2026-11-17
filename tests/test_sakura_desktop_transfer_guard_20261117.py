"""Sakura explicit-consent, pop-out, and Launch title-bar close regression.

No PySide6 / Win32 required. Native redraw must also be checked on Windows.
"""
import ast
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'


def method(file_name, name):
    tree = ast.parse((SRC / file_name).read_text(encoding='utf-8'))
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
             and node.name == name]
    assert len(nodes) == 1
    ns = {'time': time, 'Path': Path,
          'QMessageBox': SimpleNamespace(StandardButton=SimpleNamespace(Yes=1))}
    exec(compile(ast.Module(body=[nodes[0]], type_ignores=[]), '<contract>', 'exec'), ns)
    return ns[name]


class Timer:
    def __init__(self): self.stopped = False
    def stop(self): self.stopped = True


class Status:
    def __init__(self): self.text = ''; self.shown = False
    def setText(self, text): self.text = text
    def show(self): self.shown = True
    def hide(self): self.shown = False


def test_choose_existing_editor_even_with_multiple_top_level_windows():
    from external_win32_host import pick_existing_sakura_window
    found = [(1, 101, '検索'), (2, 101, 'a.txt - サクラエディタ'),
             (3, 101, 'b.txt - サクラエディタ')]
    assert pick_existing_sakura_window(found) == found[1]
    assert pick_existing_sakura_window([]) is None


def test_existing_sakura_confirmation_asks_before_setparent(monkeypatch):
    from external_win32_host import pick_existing_sakura_window
    external = types.ModuleType('external_win32_host')
    external.editor_windows = lambda *a, **k: [(1, 101, '検索'), (2, 101, 'notes.txt - サクラエディタ')]
    external.pick_existing_sakura_window = pick_existing_sakura_window
    external.editor_window_pid = lambda hwnd: 101
    external.snapshot_editor_windows = lambda app: frozenset()
    external.snapshot_editor_process_ids = lambda app: frozenset()
    native = types.ModuleType('studio_win32_host')
    native.AttachedStudioWindow = lambda *a: (_ for _ in ()).throw(AssertionError('only consent may attach'))
    class MockPanel:
        _external_pending = None
        _external_key = None
        _target = None
        _external_parked = {}
        _attached = None
        def __init__(self):
            self.host = SimpleNamespace()
            self.content_stack = SimpleNamespace(setCurrentWidget=lambda w: None)
            self.title_label = SimpleNamespace(setText=lambda s: None, setToolTip=lambda s: None)
            self.status_label = Status()
            self.called = []
        def _park_current(self): return True
        def sakura_attached(self): return False
        def _offer_existing_sakura(self, *args, **kw):
            self.called.append((args, kw))
            return True
    obj = MockPanel()
    target = SimpleNamespace(app='sakura', path='C:/notes.txt', key=('sakura', 'C:/notes.txt'))
    with patch.dict(sys.modules, {'external_win32_host': external, 'studio_win32_host': native}):
        assert method('studio_preview_panel.py', 'open_external')(obj, target) is True
    assert len(obj.called) == 1
    assert obj.called[0][0][0] is target
    assert obj.called[0][0][1:3] == (2, 101)
    assert obj.called[0][1]['open_document'] is True


def test_confirmed_existing_window_only_after_stable_pid(monkeypatch):
    native = types.ModuleType('studio_win32_host')
    actions = []
    native.AttachedStudioWindow = lambda hwnd, host: (actions.append(('attach', hwnd, host)) or SimpleNamespace(hwnd=hwnd, resize=lambda w,h: actions.append(('resize',w,h))))
    external = types.ModuleType('external_win32_host')
    external.editor_window_pid = lambda hwnd: 123
    class Panel:
        _external_key = None
        _sakura_attached_pid = None
        _sakura_transfer_consented = False
        def __init__(self, accept):
            self.host = SimpleNamespace(winId=lambda: 60, width=lambda: 700, height=lambda: 500)
            self.launcher = SimpleNamespace(ask_remote_confirmation=lambda *args, **kwargs: accept)
            self.status_label = Status()
            self._attached = None
        def _sync_popout_button(self): pass
    target = SimpleNamespace(path='C:/a.txt', key=('sakura', 'a.txt'))
    with patch.dict(sys.modules, {'studio_win32_host': native, 'external_win32_host': external}):
        panel = Panel(0)
        assert method('studio_preview_panel.py', '_offer_existing_sakura')(
            panel, target, 1234, 123, 'a.txt - サクラエディタ', open_document=False) is False
        assert actions == []
        panel = Panel(1)
        assert method('studio_preview_panel.py', '_offer_existing_sakura')(
            panel, target, 1234, 123, 'a.txt - サクラエディタ', open_document=False) is True
        assert actions == [('attach', 1234, 60), ('resize', 700, 500)]
        assert panel._sakura_attached_pid == 123 and panel._sakura_transfer_consented is True
        external.editor_window_pid = lambda hwnd: 9
        panel = Panel(1)
        assert method('studio_preview_panel.py', '_offer_existing_sakura')(
            panel, target, 1234, 123, 'a.txt - サクラエディタ', open_document=False) is False
        assert len(actions) == 2


def test_pid_reuse_after_launch_triggers_consent_not_silent_timeout():
    target = SimpleNamespace(app='sakura', path='C:/notes.txt', key=('sakura', 'notes.txt'))
    host = types.ModuleType('external_win32_host')
    host.find_new_editor_window = lambda *args: None
    host.editor_windows = lambda *a, **k: [(44, 567, 'notes.txt - サクラエディタ')]
    from external_win32_host import pick_existing_sakura_window
    host.pick_existing_sakura_window = pick_existing_sakura_window
    t = Timer()
    calls = []
    obj = SimpleNamespace(_external_pending=(target, frozenset({44}), 900, time.monotonic()),
                          _external_timer=t, _external_key=target.key,
                          _sakura_baseline_pids=frozenset({567}), _sakura_switch_from=None,
                          _attached=None, status_label=Status(),
                          _offer_existing_sakura=lambda *args, **kw: (calls.append((args,kw)) or True))
    with patch.dict(sys.modules, {'external_win32_host': host}):
        method('studio_preview_panel.py', '_poll_external')(obj)
    assert t.stopped and obj._external_pending is None
    assert len(calls) == 1 and calls[0][0][1:3] == (44, 567)
    assert calls[0][1]['open_document'] is False


def test_titlebar_x_hides_launch_even_while_sakura_is_attached():
    commands = []
    obj = SimpleNamespace(dismiss=lambda **kw: commands.append(kw))
    event = SimpleNamespace(ignore=lambda: commands.append('ignored'))
    method('app.py', 'closeEvent')(obj, event)
    assert commands == ['ignored', {'force': True}]
    source = (SRC/'app.py').read_text(encoding='utf-8')
    assert "if not force and studio_panel is not None" in source


def test_popout_restores_top_level_window_parent_and_native_frame():
    source = (SRC/'studio_win32_host.py').read_text(encoding='utf-8')
    assert 'if self.original_style & WS_CHILD else 0' in source
    assert 'GWL_EXSTYLE, self.original_exstyle' in source
    assert 'RDW_ALLCHILDREN' in source and 'SWP_SHOWWINDOW' in source
    panel = (SRC/'studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'attached.detach(foreground=True, show_window=True)' in panel
    assert 'self.popout_requested.emit()' in panel


def test_no_direct_message_box_or_process_kill_in_native_editor_route():
    panel = (SRC/'studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'QMessageBox.question(' not in panel
    assert 'QMessageBox.information(' not in panel
    assert '.terminate(' not in panel and '.kill(' not in panel


def test_popout_native_detach_restores_saved_geometry_and_redraws():
    import studio_win32_host as native
    actions = []

    class FakeWin32:
        def IsWindow(self, hwnd): return hwnd == 55
        def ShowWindow(self, hwnd, command): actions.append(('show', command))
        def SetParent(self, hwnd, parent): actions.append(('parent', parent))
        def SetWindowLongPtrW(self, hwnd, flag, value): actions.append(('style', flag, value))
        def SetWindowPos(self, hwnd, insert, x, y, w, h, flags):
            actions.append(('pos', x, y, w, h, flags))
        def RedrawWindow(self, hwnd, rect, region, flags): actions.append(('redraw', flags))
        def SetForegroundWindow(self, hwnd): actions.append(('foreground', hwnd))

    attached = object.__new__(native.AttachedStudioWindow)
    attached.u = FakeWin32()
    attached.hwnd = 55
    attached.attached = True
    attached.original_parent = 0
    attached.original_style = native.WS_POPUP | native.WS_CAPTION
    attached.original_exstyle = native.WS_EX_APPWINDOW
    attached.original_rect = (50, 60, 960, 720)
    attached.detach(foreground=True, show_window=True)
    assert attached.attached is False
    assert ('parent', 0) in actions
    assert ('style', native.GWL_STYLE, attached.original_style) in actions
    assert ('style', native.GWL_EXSTYLE, attached.original_exstyle) in actions
    assert ('pos', 50, 60, 960, 720, native.SWP_NOZORDER | native.SWP_FRAMECHANGED | native.SWP_SHOWWINDOW) in actions
    assert any(a[0] == 'redraw' for a in actions)
    assert actions[-1] == ('foreground', 55)
