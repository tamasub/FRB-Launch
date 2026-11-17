"""Regression: consented desktop Sakura must not spawn a second desktop window.

Pure-Python tests run without real Windows / Qt; validate handoff control flow.
"""
import ast
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / 'src'


def panel_method(name):
    path = SRC / 'studio_preview_panel.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = [node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(found) == 1
    ns = {'Path': Path, 'time': time,
          'QMessageBox': SimpleNamespace(StandardButton=SimpleNamespace(Yes=1))}
    exec(compile(ast.Module(body=found, type_ignores=[]), str(path), 'exec'), ns)
    return ns[name]


class Label:
    def __init__(self):
        self.text = ''
        self.tip = ''
    def setText(self, text): self.text = text
    def setToolTip(self, text): self.tip = text
    def hide(self): pass


def test_adopting_existing_sakura_does_not_launch_new_process_when_file_differs():
    events = []
    created = []
    native = types.ModuleType('studio_win32_host')

    def attach(hwnd, host):
        created.append((hwnd, host))
        return SimpleNamespace(hwnd=hwnd, attached=True,
                               resize=lambda *args: None)

    native.AttachedStudioWindow = attach
    external = types.ModuleType('external_win32_host')
    external.editor_window_pid = lambda hwnd: 23424
    target = SimpleNamespace(app='sakura', path='C:/Docs/001666.txt',
                             key=('sakura', 'c:/docs/001666.txt'))
    panel = SimpleNamespace(
        launcher=SimpleNamespace(ask_remote_confirmation=lambda *a, **kw: 1),
        host=SimpleNamespace(winId=lambda: 76, width=lambda: 700, height=lambda: 500),
        title_label=Label(), status_label=Label(), _external_key=None,
        _sakura_attached_pid=None, _sakura_transfer_consented=False,
        _sync_popout_button=lambda: None,
        _sakura_trace=lambda event, **kw: events.append((event, kw)),
        _open_sakura_next=lambda target: (_ for _ in ()).throw(
            AssertionError('Adoption must not spawn a second Sakura')))
    with patch.dict(sys.modules, {'studio_win32_host': native,
                                  'external_win32_host': external}):
        assert panel_method('_offer_existing_sakura')(
            panel, target, 131346, 23424, 'xxx.txt - サクラエディタ',
            open_document=True) is True
    assert created == [(131346, 76)]
    assert panel._external_key[0] == 'sakura'
    assert panel._external_key != target.key  # Do not pretend 001666.txt is loaded.
    assert panel._sakura_attached_pid == 23424
    assert panel._sakura_transfer_consented is True
    assert panel._external_pending is None if hasattr(panel, '_external_pending') else True
    assert '001666.txt' in panel.title_label.tip
    assert 'まだ開いていません' in panel.title_label.tip
    assert [event for event, _ in events] == [
        'CONSENT_DIALOG_CALL', 'CONSENT_DIALOG_RESULT', 'CONSENT_ATTACH_OK',
        'CONSENT_ADOPT_NO_RELAUNCH']


def test_reselecting_a_file_does_not_relaunch_borrowed_sakura():
    logs = []
    panel = SimpleNamespace(
        _external_pending=None, _attached=SimpleNamespace(hwnd=131346),
        _sakura_transfer_consented=True, _sakura_owned_windows={},
        title_label=Label(),
        _sakura_trace=lambda event, **kw: logs.append(event))
    target = SimpleNamespace(path='C:/Docs/001666.txt')
    assert panel_method('_open_sakura_next')(panel, target) is False
    assert logs == ['BORROWED_SAKURA_RELAUNCH_BLOCKED']
    assert '001666.txt' in panel.title_label.tip


def test_existing_sakura_same_file_still_marks_document_open():
    native = types.ModuleType('studio_win32_host')
    native.AttachedStudioWindow = lambda hwnd, host: SimpleNamespace(
        hwnd=hwnd, attached=True, resize=lambda *args: None)
    external = types.ModuleType('external_win32_host')
    external.editor_window_pid = lambda hwnd: 23424
    target = SimpleNamespace(app='sakura', path='C:/Docs/001666.txt',
                             key=('sakura', 'c:/docs/001666.txt'))
    panel = SimpleNamespace(
        launcher=SimpleNamespace(ask_remote_confirmation=lambda *a, **kw: 1),
        host=SimpleNamespace(winId=lambda: 76, width=lambda: 700, height=lambda: 500),
        title_label=Label(), status_label=Label(), _external_key=None,
        _sync_popout_button=lambda: None)
    with patch.dict(sys.modules, {'studio_win32_host': native,
                                  'external_win32_host': external}):
        assert panel_method('_offer_existing_sakura')(
            panel, target, 131346, 23424,
            '001666.txt - サクラエディタ', open_document=True) is True
    assert panel._external_key == target.key
