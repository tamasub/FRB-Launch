"""2026-11-23: avoid resurrection of retiring GDI HWNDs; observe untracked editors.

The tests use extracted methods and stand-in Win32 helpers. They do not touch
an actual Sakura process or GUI HWND.
"""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))


def extracted_sync():
    tree = ast.parse((SRC / 'studio_preview_panel.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'StudioPreviewPanel')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == '_sync_obsidian_ime_overlay')
    ns = {'time': NS(monotonic=lambda: 90.0)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(SRC / 'studio_preview_panel.py'), 'exec'), ns)
    return ns[node.name]


def fake_panel(*, app='sakura', switching=None):
    called = []
    attached = NS(is_ime_overlay=True, hwnd=1717,
                  sync=lambda **kw: called.append(('sync', kw)))
    panel = NS(_attached=attached,
               _external_key=(app, 'C:/docs/001.txt'),
               _sakura_guest_switch=switching,
               _sakura_trace=lambda event, **kw: called.append((event, kw)),
               _trace_sakura_parked_state=lambda guest: called.append(('inventory', guest.hwnd)),
               isVisible=lambda: True,
               host=NS(isVisible=lambda: True, width=lambda: 500, height=lambda: 350),
               _launcher_popup_hwnds=lambda: ())
    return panel, called


def test_sakura_switch_hold_does_not_re_show_old_hwnd():
    panel, calls = fake_panel(switching=('next_file',))
    with patch.dict(sys.modules, {'obsidian_popout_activation_trace': NS(poll=lambda: None)}):
        extracted_sync()(panel)
    assert not [a for a in calls if a[0] == 'sync']
    assert 'SYNC_HELD_FOR_SAKURA_SWITCH' in [a[0] for a in calls]
    assert ('inventory', 1717) in calls


def test_sakura_sync_resumes_after_switch_finishes():
    panel, calls = fake_panel(switching=('next_file',))
    panel._sakura_guest_switch = None
    with patch.dict(sys.modules, {'obsidian_popout_activation_trace': NS(poll=lambda: None)}):
        extracted_sync()(panel)
    assert [a for a in calls if a[0] == 'sync']


def test_other_guest_remains_untouched_during_sakura_switch():
    panel, calls = fake_panel(app='obsidian', switching=('next_file',))
    with patch.dict(sys.modules, {'obsidian_popout_activation_trace': NS(poll=lambda: None)}):
        extracted_sync()(panel)
    assert [a for a in calls if a[0] == 'sync']
    assert not [a for a in calls if a[0] == 'SYNC_HELD_FOR_SAKURA_SWITCH']


def test_desktop_inventory_is_observation_only():
    import sakura_window_trace
    import inspect
    src = inspect.getsource(sakura_window_trace.trace_desktop_inventory)
    for forbidden in ('SetWindowPos', 'ShowWindow', 'PostMessageW', 'SendMessageW',
                      'SetParent', 'TerminateProcess', 'MoveWindow'):
        assert forbidden not in src
    assert 'include_hidden=True' in src
    assert 'SAKURA_DESKTOP_INVENTORY' in src
