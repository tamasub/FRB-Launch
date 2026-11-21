"""Permanent Windows IME fix uses activated Qt.Tool; diagnostic trace is optional."""
import ast
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_production_slash_uses_tool_and_native_activation():
    source = (BASE / 'src/slash_exp_navigation.py').read_text(encoding='utf-8')
    ast.parse(source)
    assert 'self.setWindowFlags(Qt.WindowType.Tool |' in source
    assert 'self.activateWindow()' in source
    assert 'FRB_SLASH_IME_TOOL_WINDOW' not in source
    assert 'Qt.WindowType.FramelessWindowHint' in source
    assert 'FRB_SLASH_IME_TRACE' in source  # trace remains opt-in


def test_tool_window_has_click_away_and_app_deactivation_guard():
    source = (BASE / 'src/slash_exp_navigation.py').read_text(encoding='utf-8')
    assert 'class _SlashToolDismissGuard(QObject):' in source
    assert 'application.installEventFilter(click_guard)' in source
    assert 'application.removeEventFilter(click_guard)' in source
    assert 'application.applicationStateChanged.connect(on_app_state_changed)' in source
    assert '_slash_tool_chain_has_composition(menu)' in source


def test_diagnostic_bat_keeps_ime_trace_but_not_window_switch():
    bat = (BASE / 'diagnose_exp_keyboard_ime_tool_trial.bat').read_text(encoding='utf-8')
    assert 'FRB_SLASH_IME_TOOL_WINDOW' not in bat
    assert 'FRB_SLASH_IME_TRACE=1' in bat
    assert 'src\\app.py' in bat
