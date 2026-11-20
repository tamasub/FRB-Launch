"""Exp Keyboard Ex icon inset stays local and leaves existing icon rendering intact.

The headless tests verify both render paths get the same *Qt icon subcontrol*
position rather than item padding.  A native Windows/Qt pixel check remains
necessary to verify exact coordinates on the user's theme/style engine.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from launch_appearance import (SLASH_EXP_ICON_INSET_PX,
                               slash_exp_floating_qss,
                               context_menu_spacing_qss)


def _block(css, selector):
    pattern = rf'{re.escape(selector)}\s*\{{([^}}]*)\}}'
    matches = re.findall(pattern, css)
    assert len(matches) == 1, f'Expected exactly one style block: {selector}'
    return matches[0]


def test_both_qt_renderers_have_identical_icon_inset():
    assert SLASH_EXP_ICON_INSET_PX == 6
    for theme in ('light', 'dark'):
        for row_height in (27, 37):
            css = slash_exp_floating_qss(theme, row_height)
            for selector in ('QMenu#slashExpNavigationMenu::icon',
                             'QTreeWidget#slashExpFixedScrollList::icon'):
                style = _block(css, selector)
                assert 'position:relative;' in style
                assert f'left:{SLASH_EXP_ICON_INSET_PX}px;' in style


def test_do_not_repaint_icons_or_shift_whole_menu():
    css = slash_exp_floating_qss('light', 37)
    assert 'QMenu#slashExpNavigationMenu::item' in css
    assert 'QTreeWidget#slashExpFixedScrollList::item' in css
    assert 'border:0;border-radius:10px;' in css
    assert 'padding:5px;' in css  # popup size/position unaffected
    assert 'position:absolute;' not in css


def test_other_context_menus_unaffected():
    # The shared generic right-click style is a separate rule set.
    for theme in ('light', 'dark'):
        other_css = context_menu_spacing_qss(theme)
        assert 'slashExpNavigationMenu' not in other_css
        assert 'slashExpFixedScrollList' not in other_css
        assert 'position:relative;' not in other_css
