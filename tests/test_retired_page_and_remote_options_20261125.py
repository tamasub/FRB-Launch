"""Retired options cannot be reactivated by user state or an old caller."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
from launch_state_defaults import ensure_initial_state_ini
from remote_display_policy import normalize_remote_display_mode, mode_is_remote_window

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'src/app.py').read_text(encoding='utf8')


def method(name):
    cls = next(n for n in ast.parse(APP).body if isinstance(n, ast.ClassDef) and n.name == 'Launcher')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(normalize_remote_display_mode=normalize_remote_display_mode, mode_is_remote_window=mode_is_remote_window)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual method>', 'exec'), scope)
    return scope[name]


def test_existing_state_not_rewritten(tmp_path):
    dest = tmp_path / 'state.ini'
    raw = b'[General]\r\nhide_page_buttons=false\r\nremote_display_mode=column15\r\nexperiment_remote_15_column=true\r\ndesktop_remote_enabled=true\r\n'
    dest.write_bytes(raw)
    ensure_initial_state_ini(ROOT / 'defaults/state.ini', dest)
    assert dest.read_bytes() == raw
    assert normalize_remote_display_mode('column15', legacy_enabled=True, legacy_column15=True) == 'off'


def test_old_template_cannot_seed_retired_options(tmp_path):
    src = tmp_path / 'old.ini'
    for mode in ('remote_display_mode=column15\n', ''):
        src.write_text('[General]\nhide_page_buttons=false\nexperiment_remote_15_column=true\ndesktop_remote_enabled=true\n'+mode, encoding='utf8')
        dest = tmp_path / 'state.ini'
        ensure_initial_state_ini(src, dest)
        text = dest.read_text(encoding='utf8')
        assert 'hide_page_buttons' not in text
        assert 'experiment_remote_15_column' not in text
        assert 'remote_display_mode=off' in text
        dest.unlink()


def test_runtime_switch_cannot_enable_column15():
    refresh = Mock()
    app = NS(remote_15_mode=False, settings=Mock(), hide_remote=Mock(), footer=Mock(),
             remote_display_actions={m: Mock() for m in ('off', 'window', 'wheel')},
             expanded_view=NS(update_rail_wheel_visibility=refresh))
    switch = method('set_remote_display_mode')
    switch(app, 'column15')
    assert app.remote_display_mode == 'off'
    assert app.remote_15_mode is False
    assert app.remote_on_desktop_double_click is False
    app.hide_remote.assert_called_once()
    app.remote_display_actions['off'].setChecked.assert_called_once_with(True)
    for mode in ('window', 'wheel', 'off'):
        switch(app, mode)
        assert app.remote_display_mode == mode
        assert app.remote_15_mode is False
        assert app.remote_on_desktop_double_click is (mode == 'window')
    switch(app, 'wheel')
    method('set_remote_15_mode')(app, True)
    assert app.remote_display_mode == 'wheel'
    assert not app.remote_15_mode


def test_page_buttons_never_created_and_legacy_flag_never_read():
    expanded = (ROOT / 'src/expanded_view.py').read_text(encoding='utf8')
    assert 'hide_page_buttons' not in APP
    assert 'hide_page_buttons' not in expanded
    assert 'self.workspace_page_buttons = []' in expanded
    assert 'self.workspace_page_buttons.append(' not in expanded
    assert 'self.remote_15_mode = False' in APP
