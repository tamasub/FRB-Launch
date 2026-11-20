"""Regression: Exp Keyboard Ex has one live Qt paintEvent drawing a real frame.

This test deliberately avoids desktop Qt because the bug was a Python method
override: an earlier paintEvent was silently replaced by a later definition.
"""
import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'slash_exp_navigation.py'


def _menu_class():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    return next(item for item in tree.body
                if isinstance(item, ast.ClassDef) and item.name == 'SlashExpMenu')


def test_only_one_effective_paint_event_in_slash_exp_menu():
    handlers = [item for item in _menu_class().body
                if isinstance(item, ast.FunctionDef) and item.name == 'paintEvent']
    assert len(handlers) == 1, 'Duplicate paintEvent silently hides frame painter'


def test_effective_painter_draws_frame_on_both_scroll_and_normal_paths():
    menu = _menu_class()
    handler = next(item for item in menu.body
                   if isinstance(item, ast.FunctionDef) and item.name == 'paintEvent')
    frame = next(item for item in menu.body
                 if isinstance(item, ast.FunctionDef) and item.name == '_draw_floating_frame')
    calls = [item for item in ast.walk(handler)
             if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
             and item.func.attr == '_draw_floating_frame']
    assert len(calls) == 2, 'Normal and scrolling popups both need the outline'
    assert any(isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
               and item.func.attr == 'drawRoundedRect' for item in ast.walk(frame))
    assert any(isinstance(item, ast.Constant) and item.value == 2.5
               for item in ast.walk(frame)), 'Frame must be inset inside the rounded mask'


def test_shadow_disabled_without_changing_menu_position_or_theme():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'NoDropShadowWindowHint' in source
    assert 'self.setWindowFlag(no_shadow, True)' in source
