"""Rollback contract: the November 19 minimize-unification trial is withdrawn.

Native apps retain their earlier individual pop-out/detach workflows.
Browser tabs retain their live state across third-column hide/show.
"""
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'
STUDIO = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
EXPANDED = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
BROWSER = (SRC / 'browser_preview_panel.py').read_text(encoding='utf-8')


def test_minimize_unification_is_disconnected():
    for text in (STUDIO, EXPANDED, BROWSER):
        assert 'third_column_window_state' not in text
        assert 'park_native_window' not in text
        assert 'prepare_native_redock' not in text
        assert 'studio_release_lifecycle' not in text
        assert 'release_for_third_column(' not in text


def test_popout_and_close_regain_separate_roles():
    assert 'button.setVisible(bool(obsidian_ready or vscode_ready or sakura_ready or studio_session))' in STUDIO
    assert 'self.popout_button.clicked.connect(self.pop_out_selected)' in STUDIO
    assert 'def pop_out_selected(' in STUDIO
    assert 'def close_studio_preview(' in EXPANDED
    assert 'close_external_editors' in EXPANDED.split('def close_studio_preview(', 1)[1].split('def ', 1)[0]


def test_sakura_to_browser_still_uses_sakura_specific_safe_release():
    block = EXPANDED.split('def _show_browser_third_column(', 1)[1].split('def ', 1)[0]
    assert 'release_sakura_guest_for_browser()' in block
    assert 'self._hide_studio_preview_only()' in block


def test_browser_hide_does_not_cancel_inflight_form_or_request():
    method = BROWSER.split('def stop_preview(', 1)[1].split('def ', 1)[0]
    assert 'view.stop()' not in method
    assert 'return None' in method
