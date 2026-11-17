"""Qt-independent regression for kana->Sakura focus changes after opening."""
from pathlib import Path
import ast
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from remote_kana_target import ExternalTarget, RemoteKanaTarget


def _method(name, ns):
    src = (ROOT/'src/remote_kana_integration.py').read_text('utf-8')
    cls = next(x for x in ast.parse(src).body if isinstance(x, ast.ClassDef)
               and x.name == 'RemoteKanaIntegration')
    fn = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'kana_integration', 'exec'), ns)
    return ns[name]


class DummyAPI:
    ours = True
    current = None
    def foreground_is_ours(self):
        return self.ours
    def focused(self):
        return self.current


def _environment():
    api = DummyAPI()
    ui = NS(isVisible=lambda: True, send_button=NS(setToolTip=Mock()))
    replace = _method('_replace_target', {})
    poll = _method('_poll_external_focus', {
        'sys': NS(platform='win32'),
        'UnicodeWin32': lambda: api,
        'RemoteKanaTarget': RemoteKanaTarget,
    })
    host = NS(window=ui, target=None, _external_focus_api=api)
    host._replace_target = lambda target: replace(host, target)
    return api, ui, host, poll


def test_external_focus_can_change_after_kana_window_is_open():
    api, ui, host, poll = _environment()
    api.ours = False
    api.current = ExternalTarget(100, 110, 'サクラエディタ')
    poll(host)
    assert host.target.external == api.current
    assert 'サクラエディタ' in ui.send_button.setToolTip.call_args.args[0]

    api.current = ExternalTarget(100, 220, 'サクラエディタ')
    poll(host)
    assert host.target.external.focused_child == 220  # caret in another editor

    api.current = ExternalTarget(200, 300, 'メモ帳')
    poll(host)
    assert host.target.external.foreground == 200
    assert 'メモ帳' in ui.send_button.setToolTip.call_args.args[0]


def test_own_kana_ime_focus_does_not_replace_last_external_destination():
    api, ui, host, poll = _environment()
    api.ours = False
    api.current = ExternalTarget(100, 200, 'サクラエディタ')
    poll(host)
    destination = host.target
    api.ours = True
    api.current = None
    poll(host)
    assert host.target is destination
    ui.send_button.setToolTip.assert_called_once()


def test_external_window_without_input_clears_stale_destination():
    api, ui, host, poll = _environment()
    api.ours = False
    api.current = ExternalTarget(100, 200, 'サクラエディタ')
    poll(host)
    api.current = None
    poll(host)
    assert host.target is None
    assert '未選択' in ui.send_button.setToolTip.call_args.args[0]


def test_keyboard_close_stops_tracking_and_delayed_send_rechecks_same_target():
    code = (ROOT/'src/remote_kana_integration.py').read_text('utf-8')
    assert 'self._external_focus_timer.start()' in code
    assert 'self._external_focus_timer.stop()' in code
    assert 'self._external_focus_timer.setInterval(65)' in code
    assert 'selected=self.target' in code
    fn = _method('_finish_external_send', {'QTimer':NS(singleShot=lambda *args:None)})
    api=NS(matches=Mock(return_value=True),send_unicode=Mock())
    current=RemoteKanaTarget(external=ExternalTarget(1,2,'Sakura'),api=api)
    ui=NS(mark_sent=Mock())
    obj=NS(window=ui,target=current,_refocus_keyboard=Mock())
    # Another target chosen during the 110ms delay must invalidate the send.
    selected=RemoteKanaTarget(external=ExternalTarget(3,4,'メモ帳'),api=api)
    fn(obj,'文字',selected)
    api.send_unicode.assert_not_called()
    assert '送信先が変更' in ui.mark_sent.call_args.args[1]
    ui.mark_sent.reset_mock()
    fn(obj,'文字',current)
    api.send_unicode.assert_called_once_with('文字')
    ui.mark_sent.assert_called_with(True, '外部入力欄へ送信しました（選択中は置換）')


def test_launcher_outside_click_does_not_dismiss_live_kana():
    code=(ROOT/'src/app.py').read_text('utf-8')
    assert 'def remote_kana_active(self):' in code
    assert 'if self.remote_kana_active():' in code
    assert 'if window.remote_kana_active():' in code
    assert code.index('if window.remote_kana_active():') < code.index("DIAG.info('REMOTE_OUTSIDE_CLICK_HIDE')")
    assert 'REMOTE_OUTSIDE_CLICK_KEEP_KANA' in code
    # Existing non-kana outside click behavior is still present.
    assert 'window.hide_remote()' in code
