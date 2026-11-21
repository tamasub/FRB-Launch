"""Permanent Explorer D&D default, no visible toggle, ini rollback contract."""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from files_list_drag_settings import files_list_shell_drag_enabled
from launch_state_defaults import ensure_initial_state_ini


class FakeSettings:
    def __init__(self, value=None):
        self.raw = value
        self.asked = []
    def value(self, key, default=None):
        self.asked.append(key)
        return self.raw if self.raw is not None else default


def test_unspecified_mode_defaults_to_shell_without_writing_setting():
    settings = FakeSettings()
    assert files_list_shell_drag_enabled(settings) is True
    assert settings.asked == ['files_list_explorer_drag']


def test_false_false_like_values_reenable_qt_path():
    for value in (False, 'false', 'FALSE', '0', 'no', 'off', ' Off '):
        assert files_list_shell_drag_enabled(FakeSettings(value)) is False


def test_explicit_true_and_invalid_values_do_not_disable_proven_shell_path():
    for value in (True, 'true', 'yes', 'on', '1', 'unexpected'):
        assert files_list_shell_drag_enabled(FakeSettings(value)) is True


def test_first_run_seeds_true_and_existing_user_state_never_overwritten(tmp_path):
    template = ROOT / 'defaults' / 'state.ini'
    target = tmp_path / 'state.ini'
    ensure_initial_state_ini(template, target)
    assert 'files_list_explorer_drag=true' in target.read_text(encoding='utf-8')
    content = b'[General]\r\nfiles_list_explorer_drag=false\r\n'
    target.write_bytes(content)
    ensure_initial_state_ini(template, target)
    assert target.read_bytes() == content


def test_files_list_only_is_switched_and_button_removed():
    view = (ROOT / 'src' / 'expanded_view.py').read_text(encoding='utf-8')
    drag = (ROOT / 'src' / 'file_drag.py').read_text(encoding='utf-8')
    for module in ('files_list_drag_settings', 'file_drag', 'expanded_view', 'native_shell_drag'):
        ast.parse((ROOT / 'src' / f'{module}.py').read_text(encoding='utf-8'))
    assert 'shell_drag_button' not in view
    assert 'set_shell_drag_mode' not in view
    assert 'files_list_shell_drag_enabled(self.launcher.settings)' in view.replace('\n            ', '')
    assert 'self.native_shell_drag_mode = False' in drag  # popup / other tree unaffected
    assert 'begin_file_copy_drag(self, rows, native_shell_mode=' in drag
    assert 'super().startDrag(supported_actions)' in view
