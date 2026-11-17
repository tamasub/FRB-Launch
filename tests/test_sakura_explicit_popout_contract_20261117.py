"""Contract tests for consented Sakura transfers and separate × / pop-out.

Python AST tests run without Qt/Win32. Manual Windows tests remain mandatory.
"""
import ast
import time
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'


def method(name):
    source = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
    parsed = ast.parse(source)
    cls = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'StudioPreviewPanel')
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    ns = {'time': time}
    exec(compile(ast.Module(body=[node], type_ignores=[]), f'<sakura-{name}>', 'exec'), ns)
    return ns[name]


class Signal:
    def __init__(self): self.emissions = 0
    def emit(self): self.emissions += 1


class Timer:
    def __init__(self): self.running = False
    def start(self): self.running = True
    def stop(self): self.running = False


def test_explicit_popout_detaches_only_and_never_closes(monkeypatch):
    import external_win32_host
    monkeypatch.setattr(external_win32_host, 'editor_window_pid', lambda hwnd: 777)
    actions = []
    attached = SimpleNamespace(hwnd=123, attached=True, detach=lambda **kw: actions.append(('detach', kw)))
    signal = Signal()
    panel = SimpleNamespace(_attached=attached, _external_key=('sakura', 'a.txt'),
                            _external_pending=None, _sakura_attached_pid=777,
                            _sakura_close_timer=Timer(), _sakura_close_wait_hwnd=None,
                            _sakura_transfer_consented=True, _sakura_owned_windows={123: 777},
                            _sakura_switch_from=None, _sync_popout_button=lambda: None,
                            popout_requested=signal)
    panel.sakura_attached = lambda: True
    assert method('pop_out_sakura')(panel) is True
    assert actions == [('detach', {'foreground': True, 'show_window': True})]
    assert signal.emissions == 1
    assert panel._attached is None and panel._external_key is None
    assert panel._sakura_owned_windows == {}


def test_x_requests_only_normal_wm_close_without_detaching(monkeypatch):
    import external_win32_host, studio_win32_host
    monkeypatch.setattr(external_win32_host, 'editor_window_pid', lambda hwnd: 456)
    calls = []
    monkeypatch.setattr(studio_win32_host, 'request_editor_window_close', lambda hwnd: calls.append(hwnd))
    timer = Timer()
    attached = SimpleNamespace(hwnd=20, attached=True, detach=lambda **kw: (_ for _ in ()).throw(AssertionError('unexpected detach')))
    panel = SimpleNamespace(_attached=attached, _external_key=('sakura', 'x.txt'),
                            _external_pending=None, _sakura_attached_pid=456,
                            _sakura_transfer_consented=True,
                            _sakura_close_timer=timer, _sakura_close_wait_hwnd=None,
                            _sakura_close_requested_at=0)
    panel.sakura_attached = lambda: True
    assert method('_request_sakura_normal_close')(panel) is False  # asynchronous
    assert calls == [20] and timer.running
    assert panel._attached is attached and panel._external_key == ('sakura', 'x.txt')
    # Rapid second click does not send two WM_CLOSE messages.
    assert method('_request_sakura_normal_close')(panel) is False
    assert calls == [20]


def test_x_never_closes_unconsented_sakura(monkeypatch):
    import studio_win32_host
    monkeypatch.setattr(studio_win32_host, 'request_editor_window_close', lambda *_: (_ for _ in ()).throw(AssertionError('WM_CLOSE')))
    panel = SimpleNamespace(_attached=SimpleNamespace(hwnd=20), _external_key=('sakura','x'),
                            _external_pending=None, _sakura_transfer_consented=False)
    panel.sakura_attached=lambda: True
    assert method('_request_sakura_normal_close')(panel) is False


def test_save_cancel_keeps_embedded_sakura(monkeypatch):
    import external_win32_host
    monkeypatch.setattr(external_win32_host, 'editor_window_pid', lambda hwnd: 45)
    signal = Signal()
    panel = SimpleNamespace(_sakura_close_wait_hwnd=20, _sakura_close_timer=Timer(),
                            _sakura_attached_pid=45, _attached=SimpleNamespace(hwnd=20),
                            _external_key=('sakura','x.txt'),
                            sakura_close_completed=signal)
    method('_poll_sakura_close')(panel)
    assert panel._attached.hwnd == 20
    assert panel._external_key == ('sakura', 'x.txt')
    assert signal.emissions == 0


def test_completed_native_close_hides_only_after_hwnd_dies(monkeypatch):
    import external_win32_host
    monkeypatch.setattr(external_win32_host, 'editor_window_pid', lambda hwnd: 0)
    signal = Signal()
    panel = SimpleNamespace(_sakura_close_wait_hwnd=20, _sakura_close_timer=Timer(),
                            _sakura_attached_pid=45, _sakura_transfer_consented=True,
                            _attached=SimpleNamespace(hwnd=20),
                            _external_key=('sakura','x.txt'),
                            _sakura_owned_windows={20:45}, _sakura_switch_from=None,
                            _sync_popout_button=lambda: None, sakura_close_completed=signal)
    method('_poll_sakura_close')(panel)
    assert panel._attached is None and panel._external_key is None
    assert signal.emissions == 1


def test_button_uses_existing_vector_external_link_icon_and_consent_prompt():
    panel = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
    view = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    assert "browser_navigation_icon('external'" in panel
    assert 'QMessageBox.question(' not in panel
    assert 'QMessageBox.information(' not in panel
    assert 'self.launcher.ask_remote_confirmation(' in panel
    assert 'self.launcher.ask_remote_confirmation(' in view
    assert 'self.launcher.show_launch_notice(' in panel
    assert 'self.studio_preview.launcher = self.launcher' in view
    assert 'self.popout_button.clicked.connect(self.pop_out_sakura)' in panel
    assert 'button.setVisible(self.sakura_attached())' in panel
    assert 'self.studio_preview.popout_requested.connect(self._hide_studio_preview_only)' in view
    assert 'self.studio_preview.sakura_close_completed.connect(self._hide_studio_preview_only)' in view
    assert "if getattr(studio, 'sakura_attached'" in view
    assert "getattr(studio_panel, 'sakura_attached'" in app
    assert '.terminate(' not in panel and '.kill(' not in panel
