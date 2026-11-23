"""Ensure preview × releases Sakura through the already-working ↗ pathway.

This tests actual extracted production methods without opening Windows HWNDs.
Native GDI appearance must still be confirmed on a Windows desktop.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SRC = Path(__file__).resolve().parents[1] / 'src' / 'studio_preview_panel.py'


def method(name):
    tree = ast.parse(SRC.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'StudioPreviewPanel')
    node = next(node for node in cls.body
                if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(SRC), 'exec'), scope)
    return scope[name]


def test_x_sakura_guest_uses_explicit_popout_not_hidden_parking():
    calls = []
    attached = NS(hwnd=1234, attached=True, is_ime_overlay=True)
    panel = NS(
        _external_key=('sakura', '/tmp/a.txt'), _attached=attached,
        _external_pending=None, _external_parked={},
        _sakura_trace=lambda event, **kw: calls.append(('trace', event, kw)),
        sakura_attached=lambda: True,
        pop_out_sakura_guest=lambda: calls.append(('pop_out',)) or True,
        _park_external=lambda **kw: calls.append(('park', kw)) or True,
    )
    assert method('close_external_editors')(panel)
    assert ('pop_out',) in calls
    assert not any(x[0] == 'park' for x in calls)
    assert ('trace', 'TITLEBAR_X_POPOUT_RESULT', {'success': True}) in calls


def test_x_sakura_failed_popout_keeps_pane_and_does_not_hide():
    calls = []
    panel = NS(
        _external_key=('sakura', '/tmp/a.txt'),
        _attached=NS(hwnd=1234, attached=True, is_ime_overlay=True),
        _external_pending=None,
        sakura_attached=lambda: True,
        pop_out_sakura_guest=lambda: calls.append('failed') or False,
        _park_external=lambda **kw: calls.append('wrong-park') or True,
    )
    assert method('close_external_editors')(panel) is False
    assert calls == ['failed']
    assert panel._external_key == ('sakura', '/tmp/a.txt')


def test_x_vs_code_still_uses_existing_park_route():
    calls = []
    panel = NS(_external_key=('vscode', '/tmp/a.py'), _attached=NS(is_ime_overlay=True),
               _external_pending=None,
               _park_external=lambda **kw: calls.append(('park', kw)) or True,
               pop_out_sakura_guest=lambda: calls.append(('wrong-popout',)) or True)
    assert method('close_external_editors')(panel)
    assert calls == [('park', {})]


def test_existing_sakura_guest_popout_detaches_visible_foreground_and_emits():
    calls = []

    class Attached:
        hwnd=1234
        attached=True
        is_ime_overlay=True
        def detach(self, **kwargs):
            calls.append(('detach', kwargs))
            self.attached=False

    overlay=Attached()
    panel = NS(
        _external_key=('sakura', '/tmp/a.txt'), _attached=overlay,
        _external_pending=None, _sakura_guest_switch=None,
        _external_parked={}, _auto_ejected_keys=set(),
        _sync_popout_button=lambda: calls.append('sync'),
        popout_requested=NS(emit=lambda: calls.append('hide-packet')),
    )
    assert method('pop_out_sakura_guest')(panel)
    assert ('detach', {'foreground': True, 'show_window': True}) in calls
    assert 'hide-packet' in calls
    assert panel._attached is None and panel._external_key is None
    assert panel._external_parked[('sakura', '/tmp/a.txt')] == 1234


def test_x_panel_hides_only_after_release_acknowledged():
    view_source = Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py'
    tree = ast.parse(view_source.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == 'ExpandedLauncherView')
    fn = next(node for node in cls.body
              if isinstance(node, ast.FunctionDef) and node.name == 'close_studio_preview')
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(view_source), 'exec'), scope)
    release = scope['close_studio_preview']
    calls = []
    panel = NS(isHidden=lambda: False,
               close_external_editors=lambda: calls.append('release-refused') or False)
    obj = NS(studio_preview=panel,
             _hide_studio_preview_only=lambda: calls.append('hide'))
    release(obj)
    assert calls == ['release-refused']
