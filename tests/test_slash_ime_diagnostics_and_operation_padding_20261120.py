"""Exp Keyboard Ex: opt-in, redacted IME trace + comfortable operation header."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_operations_exp_list_first_row_top_padding_and_old_frame_contract():
    from sys import path
    path.insert(0, str(ROOT / 'src'))
    from launch_appearance import files_operation_context_qss, context_menu_spacing_qss
    for theme in ('light', 'dark'):
        qss = files_operation_context_qss(theme) + context_menu_spacing_qss(theme)
        assert 'QMenu#frbFilesContextMenu {padding:9px 5px 5px 9px;}' in qss
        assert 'QMenu#frbFilesContextMenu {border:0;border-radius:10px;}' in qss
        assert 'QMenu::item { padding:7px 9px; }' in qss


def test_trace_is_opt_in_and_text_redacted():
    source = (ROOT / 'src/slash_ime_trace.py').read_text(encoding='utf-8')
    for forbidden in ('event.text()}', 'event.preeditString()}', 'event.commitString()}'):
        assert forbidden not in source
    assert 'len(event.text())' in source
    assert 'len(event.preeditString())' in source
    assert 'len(event.commitString())' in source
    assert 'return False  # Diagnostic NEVER interferes' in source
    assert 'FRB_SLASH_IME_TRACE' in source
    assert 'exp_keyboard_ime_trace.log' in source


def test_diagnostic_instruments_both_working_and_new_editors_without_global_behavior_change():
    app = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    slash = (ROOT / 'src/slash_exp_navigation.py').read_text(encoding='utf-8')
    assert 'watch_ime_menu(self, self.filter_edit, "cascade")' in app
    assert 'watch_ime_menu(self, edit, "slash")' in slash
    assert 'checkpoint_ime(self, "input_method_received"' in slash
    assert 'checkpoint_ime(self, "after_menu_focus_request")' in slash
    assert 'if os.environ.get("FRB_SLASH_IME_TRACE") == "1":' in app
    assert 'if os.environ.get("FRB_SLASH_IME_TRACE") == "1":' in slash
    # Unconditional import of Qt-dependent diagnostics can break existing
    # test doubles and would turn this into an intrusive production dependency.
    assert 'from slash_ime_trace import' not in slash.split('def slash_source_from_breadcrumb', 1)[0]
    ast.parse(app)
    ast.parse(slash)


def test_diagnostic_launcher_uses_python_source_not_stale_exe():
    source = (ROOT / 'diagnose_exp_keyboard_ime.bat').read_text(encoding='utf-8')
    assert 'FRB_SLASH_IME_TRACE=1' in source
    assert 'FRB_SLASH_IME_LOG=' in source
    assert '.venv\\Scripts\\python.exe' in source
    assert 'src\\app.py' in source
