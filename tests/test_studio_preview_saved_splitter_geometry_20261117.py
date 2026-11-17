"""Studio width/position persistence with a closed two-column Files layout.

Pure geometry tests; physical Windows/Qt native child constraints remain an
explicit manual acceptance check.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import sys

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from preview_splitter_layout import (plan_restored_preview_sizes, saved_preview_columns)


def _method(name):
    tree = ast.parse((SRC / 'expanded_view.py').read_text(encoding='utf-8'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                 and n.name == 'ExpandedLauncherView')
    node = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<studio-preview-geometry>', 'exec'), scope)
    return scope[name]


def test_saved_three_columns_take_priority_over_unrelated_closed_two_column_width():
    # Session ended at [210, 170, 900]. Next startup has a 350px first pane.
    # The old clamp would silently shrink Studio to 780px even on a same-size window.
    restored = plan_restored_preview_sizes([350, 930], 3, 2, 900, '210|170|900')
    assert restored == [210, 170, 900]


def test_legacy_width_only_prefers_preview_by_borrowing_from_files_exp():
    restored = plan_restored_preview_sizes([350, 930], 3, 2, 900)
    assert restored == [210, 170, 900]


def test_hidden_browser_preview_slot_kept_at_zero():
    # Browser was created first, but Studio is the fourth physical child.
    assert plan_restored_preview_sizes([360, 920], 4, 3, 850, '225|205|850') == [225, 205, 0, 850]


def test_real_narrow_screen_falls_back_to_safe_minima_without_discarding_settings():
    sizes = plan_restored_preview_sizes([300, 500], 3, 2, 950,
                                        '210|170|950', min_first_width=190,
                                        min_list_width=170)
    assert sizes == [190, 170, 440]


def test_invalid_saved_geometry_falls_back_to_legacy_width():
    for value in ('', '200|180', '200|abc|400', '-1|180|400', '200|180|200', None):
        assert saved_preview_columns(value) is None
        sizes = plan_restored_preview_sizes([350, 930], 3, 2, 690, value)
        assert sizes == [350, 240, 690]


def test_current_preview_sizes_saved_to_state_and_synced_on_drag():
    writes = {}
    flushed = []
    pane = NS(isHidden=lambda: False)
    view = NS(browser_preview=None, studio_preview=pane, _preview_layout_restoring=False,
              files_splitter=NS(indexOf=lambda p: 3, sizes=lambda: [215, 180, 0, 885]),
              launcher=NS(settings=NS(setValue=lambda k, v: writes.__setitem__(k, v),
                                      sync=lambda: flushed.append(True))))
    _method('_save_active_preview_width')(view)
    assert writes['workspace_files_studio_preview_width'] == 885
    assert writes['workspace_files_studio_preview_splitter_sizes'] == '215|180|885'
    assert flushed == [True]


def test_restore_in_progress_does_not_overwrite_saved_geometry():
    writes = []
    pane = NS(isHidden=lambda: False)
    view = NS(browser_preview=None, studio_preview=pane, _preview_layout_restoring=True,
              files_splitter=NS(indexOf=lambda p: 2, sizes=lambda: [350, 610, 320]),
              launcher=NS(settings=NS(setValue=lambda *args: writes.append(args),
                                      sync=lambda: writes.append('sync'))))
    _method('_save_active_preview_width')(view)
    assert writes == []


def test_restoration_after_qt_settles_prefers_previously_saved_positions():
    updates = []
    pane = NS(isHidden=lambda: False)
    splitter = NS(indexOf=lambda p: 3, sizes=lambda: [350, 270, 0, 660],
                  setSizes=lambda values: updates.append(values))
    view = NS(files_splitter=splitter, _studio_preview_base_sizes=[350, 930],
              launcher=NS(files_root_hidden_mode=False, files_exp_embedded_mode=False),
              _preview_layout_restoring=True)
    _method('_restore_visible_preview_width')(view, pane, 900, 170, '210|170|900')
    assert updates == [[210, 170, 0, 900]]
    assert view._preview_layout_restoring is False


def test_tiny_launch_frame_falls_back_without_open_document_exception():
    sizes = plan_restored_preview_sizes([100, 160], 3, 2, 900, '210|170|900')
    assert len(sizes) == 3 and sum(sizes) >= 260


def test_remote_15_minimum_keeps_wheel_lane_from_collapsing():
    sizes = plan_restored_preview_sizes([470, 930], 3, 2, 950,
                                        '220|230|950', min_first_width=386,
                                        min_list_width=170)
    assert sizes == [386, 170, 844]
