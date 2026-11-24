"""FRB Commander v0.1: definition, paths, argv and original Keyboard Ex isolation."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from commander.viewdef import (build_argv, companion_viewdef, read_viewdef,
    resolve_initial_directory, validate_viewdef, visible_steps)
from context_menu_config import load_context_menus, visible_context_entries
from test_slash_exp_navigation_20261118 import nav


@pytest.fixture
def script_pair(tmp_path):
    script = tmp_path / 'Export-DiffToJson.ps1'
    script.write_text('param()\n', encoding='utf-8')
    example = ROOT / 'examples/commander/Export-DiffToJson.viewdef'
    definition = json.loads(example.read_text(encoding='utf-8'))
    script.with_suffix('.viewdef').write_text(example.read_text(encoding='utf-8'), encoding='utf-8')
    return script, definition


def test_viewdef_companion_and_declared_right_clicked_script(script_pair):
    script, definition = script_pair
    assert companion_viewdef(script) == script.with_suffix('.viewdef')
    assert read_viewdef(script) == definition
    assert validate_viewdef(definition, script)
    other = script.parent / 'another.ps1'
    other.write_text('param()')
    assert companion_viewdef(other) is None
    bad = json.loads(json.dumps(definition))
    bad['script']['file'] = '../Export-DiffToJson.ps1'
    with pytest.raises(ValueError, match='一致しません'):
        validate_viewdef(bad, script)


def test_source_choices_no_extra_parameters_and_safe_argv(script_pair):
    script, d = script_pair
    prefix = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script.resolve())]
    for source, args in [('working_tree', []), ('staged', ['-Mode', 'Staged']),
                         ('head', ['-Mode', 'Head'])]:
        assert build_argv(d, {'source': source}, script) == prefix + args
    assert build_argv(d, {'source': 'commit_range', 'range': 'main..HEAD'}, script)[-2:] == [
        '-Range', 'main..HEAD']


def test_filepair_source_then_two_file_steps_and_separate_argv(script_pair):
    script, d = script_pair
    a = script.parent / 'a space.json'
    b = script.parent / '日本語 b.json'
    a.write_text('{}')
    b.write_text('{}')
    values = {'source': 'file_pair', 'from_file': str(a), 'to_file': str(b)}
    assert [s['id'] for s in visible_steps(d, values)] == ['source', 'from_file', 'to_file']
    assert build_argv(d, values, script)[-6:] == [
        '-Mode', 'FilePair', '-FromFile', str(a), '-ToFile', str(b)]
    with pytest.raises(ValueError, match='比較先'):
        build_argv(d, {'source': 'file_pair', 'from_file': str(a)}, script)
    with pytest.raises(ValueError, match='見つかりません'):
        build_argv(d, {'source': 'file_pair', 'from_file': str(a),
                       'to_file': str(b.parent/'missing.json')}, script)
    with pytest.raises(ValueError, match='候補'):
        build_argv(d, {'source': 'evil'}, script)


def test_initial_location_uses_workspace_root_and_parent_of_selected_file(script_pair):
    script, d = script_pair
    a = script.parent / 'nested' / 'a.json'
    a.parent.mkdir()
    a.write_text('{}')
    from_step, to_step = d['steps'][2:4]
    assert resolve_initial_directory(from_step, {}, script=script,
        workspace_root=script.parent) == script.parent
    assert resolve_initial_directory(from_step, {}, script=script,
        workspace_root=script.parent/'not-exist') == script.parent
    assert resolve_initial_directory(to_step, {'from_file': str(a)}, script=script) == a.parent
    with pytest.raises(ValueError, match='先行ファイル'):
        resolve_initial_directory(to_step, {}, script=script)


def test_unknown_selector_is_not_executed(script_pair):
    script, d = script_pair
    bad = json.loads(json.dumps(d))
    bad['steps'][2]['selector']['type'] = 'arbitrary_shell_command'
    with pytest.raises(ValueError, match='keyboard_ex.file'):
        validate_viewdef(bad, script)
    bad2 = json.loads(json.dumps(d))
    bad2['steps'][0]['choices'][-1]['args'][-1] = '${nonexistent}'
    with pytest.raises(ValueError, match='引数テンプレート'):
        validate_viewdef(bad2, script)


def test_context_menu_is_declared_and_valid():
    menus = load_context_menus(ROOT / 'config/context_menu_options.json')
    actions = [entry.get('action_id') for entry in menus['file']]
    assert 'commander_run' in actions
    assert 'commander_run' in [e.get('action_id') for e in visible_context_entries(
        menus['file'], {'commander_run'})]
    assert 'commander_run' not in [e.get('action_id') for e in menus['folder']]


def test_existing_keyboard_ex_file_action_return_path_only(nav, tmp_path):
    from test_slash_exp_navigation_20261118 import make_launcher, Panel
    mod, keys = nav
    folder = tmp_path / 'work'
    folder.mkdir()
    target = folder / 'diff from.json'
    target.write_text('{}', encoding='utf-8')
    launcher, calls = make_launcher()
    root = mod.physical_folder_source(launcher, str(folder))
    selected = []
    menu = mod.SlashExpMenu(launcher, Panel([]), source_item=root)
    menu._file_selection_callback = selected.append
    assert menu._current_folder_item() is None
    rows = menu._items()
    file_item = next(row for row in rows if row.text() == target.name)
    assert menu._commit_terminal(file_item) is True
    assert selected == [str(target)]
    assert calls == []


def test_picker_right_selects_file_without_launching_it(nav, tmp_path):
    from test_slash_exp_navigation_20261118 import make_launcher, Panel, Event
    mod, keys = nav
    folder = tmp_path/'workspace'
    folder.mkdir()
    file = folder/'some file.json'
    file.write_text('v1', encoding='utf-8')
    launcher, launch_calls = make_launcher()
    selected = []
    menu = mod.SlashExpMenu(launcher, Panel([]),
        source_item=mod.physical_folder_source(launcher, str(folder)))
    menu._file_selection_callback = selected.append
    menu.populate()
    menu.popup(mod.QPoint(0, 0))
    action = next(a for a,item in menu._action_items.items() if item.text() == file.name)
    menu.setActiveAction(action)
    menu.keyPressEvent(Event(keys.Key_Right))
    assert selected == [str(file)]
    assert launch_calls == []
    assert not menu.isVisible()


def test_picker_folder_enter_explores_instead_of_changing_launch_list(nav, tmp_path):
    from test_slash_exp_navigation_20261118 import make_launcher, Panel, Event
    mod, keys = nav
    folder = tmp_path/'workspace'
    child = folder/'nested'
    child.mkdir(parents=True)
    file = child/'inside.json'
    file.write_text('{}', encoding='utf-8')
    launcher, launch_calls = make_launcher()
    selected = []
    menu = mod.SlashExpMenu(launcher, Panel([]),
        source_item=mod.physical_folder_source(launcher, str(folder)))
    menu._file_selection_callback = selected.append
    menu.populate()
    menu.popup(mod.QPoint(0, 0))
    action = next(a for a,item in menu._action_items.items() if item.text() == 'nested')
    menu.setActiveAction(action)
    menu.keyPressEvent(Event(keys.Key_Enter))
    submenu = menu._submenus[action]
    assert submenu.isVisible()
    item = next(a for a, row in submenu._action_items.items() if row.text() == file.name)
    submenu.setActiveAction(item)
    submenu.keyPressEvent(Event(keys.Key_Right))
    assert selected == [str(file)]
    assert launch_calls == []
