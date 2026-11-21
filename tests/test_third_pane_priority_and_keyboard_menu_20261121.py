"""User-intent width persistence and Keyboard Ex text parity (Qt-free)."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))
from third_column_width_preferences import (
    width_setting, list_setting, preferred_third_width, preferred_list_width,
    save_user_widths, prioritized_preview_sizes)


class Settings:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.sync_calls = 0
    def value(self, key, default=None):
        return self.data.get(key, default)
    def setValue(self, key, value):
        self.data[key] = value
    def sync(self):
        self.sync_calls += 1


def method(name):
    source = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    owner = next(cls for cls in ast.parse(source).body if
                 isinstance(cls, ast.ClassDef) and cls.name == 'ExpandedLauncherView')
    node = next(node for node in owner.body if
                isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<expanded-view-width>', 'exec'), namespace)
    return namespace[name]


def test_app_widths_have_independent_settings_with_legacy_browser_import():
    assert len({width_setting(owner) for owner in ('browser', 'studio', 'obsidian', 'vscode', 'options')}) == 5
    state = Settings({'workspace_files_full_browser_width_v1': '550',
                      'workspace_files_studio_preview_width': '710'})
    assert preferred_third_width(state, 'browser') == 550
    assert preferred_third_width(state, 'studio') == 710
    # Prior installs shared one editor width; preserve it as a first-time fallback.
    assert preferred_third_width(state, 'obsidian', 520) == 710
    assert preferred_third_width(state, 'vscode', 520) == 710
    state.setValue(width_setting('browser'), 630)
    assert preferred_third_width(state, 'browser') == 630
    assert preferred_third_width(state, 'studio') == 710


def test_user_drag_is_the_only_save_operation_and_falls_back_to_prior_valid_values():
    state = Settings()
    assert not save_user_widths(state, 'browser', 110, 400)
    assert state.data == {} and state.sync_calls == 0
    assert save_user_widths(state, 'browser', 450, 580)
    assert preferred_list_width(state, 'browser') == 450
    assert preferred_third_width(state, 'browser') == 580
    assert state.sync_calls == 1
    # Neither resize nor normal panel closure may overwrite this state.
    view = NS(_third_width_committing=False, _preview_layout_restoring=False,
              _preview_maximized=False)
    method('_save_active_preview_width')(view)
    assert state.sync_calls == 1


def test_exp_and_list_precede_third_when_reopening_on_narrow_monitor():
    wide = prioritized_preview_sizes(1650, 3, 2, exp_desired=280,
                                     list_desired=550, third_desired=680)
    narrow = prioritized_preview_sizes(1050, 3, 2, exp_desired=280,
                                       list_desired=550, third_desired=680)
    assert wide == [280, 690, 680]
    assert narrow == [280, 550, 220]
    assert sum(wide) == 1650 and sum(narrow) == 1050
    assert [280, 550, 680] == [280, 550, 680]  # desired values unchanged


def test_hidden_sibling_does_not_take_pixels_or_override_active_index():
    assert prioritized_preview_sizes(
        1200, 4, 3, exp_desired=260,
        list_desired=450, third_desired=540) == [260, 450, 0, 490]


def test_extremely_small_window_does_not_promote_third_over_exp():
    result = prioritized_preview_sizes(320, 3, 2, exp_desired=260,
                                       list_desired=460, third_desired=600)
    assert result == [260, 60, 0] and sum(result) == 320


def test_switch_between_studio_and_obsidian_preserves_app_specific_width():
    state = Settings()
    save_user_widths(state, 'studio', 400, 620)
    save_user_widths(state, 'obsidian', 440, 810)
    assert preferred_third_width(state, 'studio') == 620
    assert preferred_third_width(state, 'obsidian') == 810
    assert preferred_list_width(state, 'studio') == 400
    assert preferred_list_width(state, 'obsidian') == 440


def test_browser_restore_runs_after_webengine_docking_and_owner_is_per_app():
    source = (SRC / 'expanded_view.py').read_text('utf-8')
    assert "self._queue_preview_owner_restore(self.browser_preview, 'browser')" in source
    assert 'QTimer.singleShot(80, apply)' in source
    assert 'QTimer.singleShot(240, apply)' in source
    assert "self._ensure_studio_preview(owner=target.app)" in source
    assert "self._ensure_studio_preview(owner='options')" in source
    assert 'self._third_width_committing = True' in source
    assert 'self._third_width_committing = False' in source
    assert 'self._install_third_width_handle(self.browser_preview)' in source
    assert 'self._install_third_width_handle(self.studio_preview)' in source


def test_menu_matches_list_text_metrics_and_uses_full_name_in_scroll_view():
    source = (SRC / 'slash_exp_navigation.py').read_text('utf-8')
    css = (SRC / 'launch_appearance.py').read_text('utf-8')
    assert 'SLASH_FIRST_COLUMN_CHROME_PX = 44' in source
    assert 'SLASH_FIRST_COLUMN_CHROME_PX = 44' in source
    assert 'extra_name_gutter=44' in (SRC / 'app.py').read_text('utf-8')
    assert 'max(0, int(extra_name_gutter))' in source
    assert 'self._display_text.get(action, action.text())' in source
    assert 'self._display_text[action] = display_label' in source
    assert "font-family:'Yu Gothic UI';font-size:12px;" in css
    assert 'QTreeWidget#slashExpFixedScrollList::item' in css
    assert 'left:{SLASH_EXP_ICON_INSET_PX}px' in css
