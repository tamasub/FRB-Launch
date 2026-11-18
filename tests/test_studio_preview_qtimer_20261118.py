"""Regression: reopening a docked Studio must not shadow module-level QTimer.

No GUI needed: extract the production method unchanged and exercise its
already-visible branch (the branch that previously raised UnboundLocalError).
"""
import ast
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py'


def _method():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    candidates = [node for node in ast.walk(tree)
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.name == '_ensure_studio_preview']
    assert len(candidates) == 1
    return candidates[0]


def test_preview_reopen_uses_global_qtimer_not_conditional_local_import():
    timer_calls = []
    events = []
    method = _method()
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {
        'os': SimpleNamespace(name='nt'),
        'QTimer': SimpleNamespace(singleShot=lambda delay, callback:
                                  timer_calls.append((delay, callback))),
    }
    exec(compile(module, str(SOURCE), 'exec'), ns)
    view = SimpleNamespace(
        _workspace_mode='files',
        browser_preview=None,
        studio_preview=SimpleNamespace(isHidden=lambda: False),
        queue_rail_wheel_position=lambda: events.append('reposition'),
    )
    assert ns['_ensure_studio_preview'](view) is True
    assert events == ['reposition']
    assert timer_calls and timer_calls[0][0] == 80


def test_only_module_level_qtimer_is_used_by_preview_method():
    method = _method()
    local_timers = [n for n in ast.walk(method)
                    if isinstance(n, ast.ImportFrom)
                    and any(alias.name == 'QTimer' for alias in n.names)]
    assert local_timers == []
