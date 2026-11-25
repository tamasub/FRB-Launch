"""FRB Launch リモコン3択（1.5列廃止）／ぐりぐり丸ボタン・静的契約テスト。"""
from pathlib import Path
import sys
import ast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))

from remote_display_policy import normalize_remote_display_mode, mode_is_remote_window
from launch_state_defaults import _template_values


def test_three_modes_and_retired_flags():
    for mode in ('off', 'window', 'wheel'):
        assert normalize_remote_display_mode(mode) == mode
        assert mode_is_remote_window(mode) is (mode == 'window')
        assert normalize_remote_display_mode(mode, legacy_enabled=True, legacy_column15=True) == mode
    assert normalize_remote_display_mode(None, legacy_enabled='true') == 'window'
    assert normalize_remote_display_mode(None, legacy_column15='true') == 'off'
    assert normalize_remote_display_mode(None, legacy_enabled=True, legacy_column15=True) == 'off'
    assert normalize_remote_display_mode(None) == 'off'
    assert normalize_remote_display_mode('invalid', legacy_enabled=True) == 'off'
    assert normalize_remote_display_mode('COLUMN15', legacy_enabled=True) == 'off'
    assert not mode_is_remote_window('column15')


def test_state_ini_default_matches_off_and_seed_recognizes_enum():
    state = _template_values(ROOT / 'defaults' / 'state.ini')
    assert state['remote_display_mode'] == 'off'
    assert state['desktop_remote_enabled'] == 'false'
    assert 'experiment_remote_15_column' not in state
    assert 'hide_page_buttons' not in state


def test_options_is_exclusive_submenu_and_legacy_state_writes():
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    for label in ('使用しない', 'リモコンウィンドウ 別Window', 'ぐりぐりボタンのみ'):
        assert label in app
    assert 'リモコンウィンドウ 1.5列へ表示' not in app
    assert 'self.remote_display_group.setExclusive(True)' in app
    assert "self.settings.setValue('remote_display_mode', mode)" in app
    assert "self.settings.setValue('desktop_remote_enabled', self.remote_on_desktop_double_click)" in app
    assert "self.settings.setValue('experiment_remote_15_column'" not in app
    assert "if mode in ('off', 'wheel'):" in app


def test_round_pad_is_child_of_workspace_and_follows_splitter():
    view = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    ast.parse(view)
    assert 'self.rail_wheel = RoundRailWheelPad(self)' in view
    assert 'QRegion.RegionType.Ellipse' in view
    assert 'self.rail_wheel.command.connect(self.rail_wheel_command)' in view
    assert 'self.rail_wheel.side_changed.connect(self.rail_wheel_select_side)' in view
    assert 'self.files_splitter.splitterMoved.connect(' in view
    assert 'handle.mapTo(self,' in view
    assert 'def resizeEvent(self, event):' in view
    assert "self._workspace_mode = 'browser'\n        self.update_rail_wheel_visibility()" in view
    assert "self._workspace_mode = 'files'\n        self.files_content_stack.setCurrentWidget(self.files_group)\n        self.update_rail_wheel_visibility()" in view


def test_source_syntax():
    for name in ('app.py', 'expanded_view.py', 'launch_state_defaults.py',
                 'remote_display_policy.py'):
        ast.parse((SRC / name).read_text(encoding='utf-8'))


def test_right_click_reuses_existing_context_menu_with_embedded_pad():
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    assert 'def _active_remote_wheel_pad(self):' in app
    assert 'pad = self._active_remote_wheel_pad()' in app
    assert 'menu.popup(pad.mapToGlobal(QPoint(pad.width() + 4, 0)))' in app
