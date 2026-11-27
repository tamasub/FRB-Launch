"""Folder-only Keyboard Ex selection and Commander argument contract."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from commander.viewdef import build_argv, read_viewdef, validate_viewdef
from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Event


@pytest.fixture
def pair():
    script = ROOT / 'tools/FRB_Commander/FRB_Commander_source_steps/cmd_count_source_steps.ps1'
    return script, read_viewdef(script)


def test_schema_and_both_argv_routes(pair, tmp_path):
    from jsonschema import Draft202012Validator
    script, definition = pair
    schema = json.loads((ROOT / 'defs/commander/frb_commander_viewdef_schema_v0_1.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(definition)
    for path in [ROOT/'examples/commander/Export-DiffToJson.viewdef', ROOT/'tools/FRB_Commander/LaunchConfigMigration/Migrate-LaunchConfig.viewdef']:
        validator.validate(json.loads(path.read_text(encoding='utf-8-sig')))
    folder = tmp_path / '日本語 space & folder'
    folder.mkdir()
    for source, extra in [('count', []), ('count_git_diff', ['-GitDiff'])]:
        assert build_argv(definition, {'source': source, 'root': str(folder)}, script)[5:] == ['-Root', str(folder), *extra]
    invalid = copy.deepcopy(definition)
    invalid['steps'][1]['selector']['type'] = 'keyboard_ex.file'
    assert not validator.is_valid(invalid)
    with pytest.raises(ValueError, match='keyboard_ex.folder'):
        validate_viewdef(invalid, script)


def test_folder_requires_existing_directory(pair, tmp_path):
    script, definition = pair
    f = tmp_path / 'file.txt'
    f.touch()
    for target in (f, tmp_path / 'missing'):
        with pytest.raises(ValueError, match='フォルダーが見つかりません'):
            build_argv(definition, {'source': 'count', 'root': str(target)}, script)


def make_picker(mod, folder):
    launcher, calls = make_launcher()
    selected = []
    menu = mod.SlashExpMenu(launcher, Panel([]), source_item=mod.physical_folder_source(launcher, str(folder)))
    menu._file_selection_callback = selected.append
    menu._selection_kind = 'folder'
    menu.populate()
    menu.popup(mod.QPoint(0, 0))
    return menu, selected, calls


def choose(menu, keys, name, key):
    action = next(a for a, item in menu._action_items.items() if item.text() == name)
    menu.setActiveAction(action)
    menu.keyPressEvent(Event(key))
    return action


def test_enter_returns_child_not_launch_navigation(nav, tmp_path):
    mod, keys = nav
    child = tmp_path / '日本語 empty'
    child.mkdir()
    (tmp_path / 'not-a-folder.py').touch()
    menu, selected, calls = make_picker(mod, tmp_path)
    assert [i.text() for i in menu._action_items.values()] == ['（このフォルダーを選択）', child.name]
    choose(menu, keys, child.name, keys.Key_Enter)
    assert selected == [str(child)] and calls == [] and not menu.isVisible()


def test_right_enters_empty_child_then_selects_current(nav, tmp_path):
    mod, keys = nav
    child = tmp_path / 'empty'
    child.mkdir()
    menu, selected, calls = make_picker(mod, tmp_path)
    branch = choose(menu, keys, child.name, keys.Key_Right)
    sub = menu._submenus[branch]
    assert sub.isVisible() and selected == []
    choose(sub, keys, '（このフォルダーを選択）', keys.Key_Right)
    assert selected == [] and sub.isVisible()
    choose(sub, keys, '（このフォルダーを選択）', keys.Key_Enter)
    assert selected == [str(child)] and calls == []


def test_empty_root_current_row_and_escape(nav, tmp_path):
    mod, keys = nav
    menu, selected, calls = make_picker(mod, tmp_path)
    choose(menu, keys, '（このフォルダーを選択）', keys.Key_Escape)
    assert selected == [] and calls == [] and not menu.isVisible()
    menu, selected, calls = make_picker(mod, tmp_path)
    choose(menu, keys, '（このフォルダーを選択）', keys.Key_Enter)
    assert selected == [str(tmp_path)] and calls == []
