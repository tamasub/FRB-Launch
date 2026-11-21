"""Auto-eject contract for an incoming third-column app, without Windows GUI."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def fn(name, *, source='studio_preview_panel.py', env=None):
    tree = ast.parse((ROOT / 'src' / source).read_text(encoding='utf-8'))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef)
               and x.name == ('StudioPreviewPanel' if source == 'studio_preview_panel.py' else 'ExpandedView'))
    node = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name)
    namespace = {} if env is None else dict(env)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), name, 'exec'), namespace)
    return namespace[name]


def test_external_overlay_switch_requests_visible_desktop_release():
    calls = []
    panel = NS(_external_key=('obsidian', 'c:/vault/a.md'),
               _attached=NS(is_ime_overlay=True),
               _park_external=lambda **kwargs: calls.append(kwargs) or True)
    assert fn('auto_release_external_for_switch')(panel)
    assert calls == [{'desktop': True}]


def test_legacy_sakura_stays_protected():
    panel = NS(_external_key=('sakura', 'c:/docs/a.txt'),
               _attached=NS(is_ime_overlay=False), _park_external=Mock())
    assert fn('auto_release_external_for_switch')(panel) is False
    panel._park_external.assert_not_called()


def test_studio_switch_requires_owner_release_before_new_app():
    callback = Mock()
    panel = NS(_target=('c:/data.json',), _process=NS(poll=lambda: None),
               _studio_popout_pending=False, _after_studio_popout=None,
               pop_out_studio=Mock(return_value=True))
    assert fn('request_studio_autoswitch')(panel, callback)
    assert panel._after_studio_popout is callback
    panel.pop_out_studio.assert_called_once()


def test_studio_refusal_does_not_run_callback_or_lose_current_data():
    callback = Mock()
    target = ('c:/data.json',)
    panel = NS(_target=target, _process=NS(poll=lambda: None),
               _studio_popout_pending=False, _after_studio_popout=None,
               pop_out_studio=Mock(return_value=False))
    assert not fn('request_studio_autoswitch')(panel, callback)
    assert panel._after_studio_popout is None
    assert panel._target is target
    callback.assert_not_called()


def test_studio_ack_then_desktop_release_then_next_app():
    steps = []
    class Guest:
        def detach(self, **kwargs):
            steps.append(('release', kwargs))
    panel = NS(_studio_popout_pending=True,
               _after_studio_popout=lambda: steps.append(('next_app',)),
               _attached=Guest(), _process=NS(), _target=('a.json',),
               _launch_pipe_token='token', _launch_switch_pending=('a.json',),
               _timer=NS(stop=lambda: steps.append(('timer_stop',))),
               _sync_popout_button=lambda: steps.append(('sync',)),
               popout_requested=NS(emit=lambda: steps.append(('popout_signal',))),
               status_label=NS(setText=lambda x: None, show=lambda: None))
    QTimer = NS(singleShot=lambda delay, callback: callback())
    assert fn('_finish_studio_popout',env={'QTimer': QTimer})(panel,'OK')
    assert steps[0] == ('release', {'foreground': True, 'show_window': True})
    assert steps[-1] == ('next_app',)
    assert panel._attached is None and panel._process is None and panel._target is None


def test_studio_refuses_ack_keeps_current_occupied():
    callback = Mock()
    win = NS(detach=Mock())
    panel = NS(_studio_popout_pending=True, _after_studio_popout=callback,
               _attached=win, _target=('a.json',), _process=NS(),
               status_label=NS(setText=lambda x: None, show=lambda: None),
               _sync_popout_button=Mock())
    assert fn('_finish_studio_popout',env={'QTimer': NS(singleShot=lambda *a: None)})(panel,'CANCEL') is None
    assert panel._attached is win
    win.detach.assert_not_called()
    callback.assert_not_called()
