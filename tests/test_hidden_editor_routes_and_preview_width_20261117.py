"""New November 17 safety gates: three app-specific opt-ins, .md routing and pane width."""
from pathlib import Path
import ast
import json

from third_column_host_options import embedded_editor_enabled
from external_preview_route import (ExternalPreviewTarget, external_preview_target,
                                    standalone_editor_command, launch_external_standalone)
from preview_splitter_layout import restored_preview_width, preview_sizes

SRC = Path(__file__).resolve().parents[1] / 'src'


def test_hidden_option_missing_and_corrupt_both_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    assert all(not embedded_editor_enabled(tmp_path, app) for app in ('studio', 'obsidian', 'sakura'))
    folder = tmp_path / 'FRBLaunch'
    folder.mkdir()
    filename = folder / 'state.ini'
    filename.write_text('broken INI', encoding='utf-8')
    assert not embedded_editor_enabled(tmp_path, 'studio')
    filename.write_text('[General]\nembed_studio=maybe\nembed_obsidian=2\n'
                        'embed_sakura=false\n', encoding='utf-8')
    assert all(not embedded_editor_enabled(tmp_path, app) for app in ('studio', 'obsidian', 'sakura'))


def test_explicit_per_app_flags_and_no_unknown_apps(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    folder = tmp_path / 'FRBLaunch'
    folder.mkdir()
    config = folder / 'state.ini'
    config.write_text('[General]\nembed_studio=true\nembed_obsidian=false\n'
                      'embed_sakura=1\n', encoding='utf-8')
    assert embedded_editor_enabled(tmp_path, 'studio')
    assert embedded_editor_enabled(tmp_path, 'sakura')
    assert not embedded_editor_enabled(tmp_path, 'obsidian')
    assert not embedded_editor_enabled(tmp_path, 'browser')


def test_legacy_third_column_json_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    folder = tmp_path / 'UserConfig'
    folder.mkdir()
    (folder / 'third_column_hosts.json').write_text(
        json.dumps({'embed_studio': True, 'embed_obsidian': True,
                    'embed_sakura': True}), encoding='utf-8')
    assert all(not embedded_editor_enabled(tmp_path, app)
               for app in ('studio', 'obsidian', 'sakura'))


def test_all_markdown_paths_route_to_obsidian_without_vault_check(tmp_path):
    for name in ('Documents memo.MD', 'free note.md'):
        path = tmp_path / name
        path.write_text('# okay', encoding='utf-8')
        target = external_preview_target({'_browse_file': str(path)},
                                         vault_lookup=lambda _: None)
        assert target == ExternalPreviewTarget('obsidian', str(path))


def test_obsidian_standalone_explicit_executable_not_default_association(tmp_path):
    exe = tmp_path / 'Obsidian.exe'; exe.write_text('test')
    note = tmp_path / 'note.md'; note.write_text('# note')
    target = ExternalPreviewTarget('obsidian', str(note))
    assert standalone_editor_command(target, obsidian_lookup=lambda: str(exe)) == [str(exe), str(note)]
    calls = []
    launch_external_standalone(target, popen=lambda args, cwd: calls.append((args, cwd)),
                               obsidian_lookup=lambda: str(exe))
    assert calls == [([str(exe), str(note)], str(tmp_path))]


def test_preview_width_saved_and_clamped_without_changing_two_columns():
    assert restored_preview_width('610', 380, [300, 1000], 230) == 610
    assert restored_preview_width('bad', 380, [300, 1000], 230) == 380
    assert restored_preview_width('1500', 380, [300, 1000], 230) == 770
    assert restored_preview_width('610', 380, [300, 500], 230) == 270
    assert preview_sizes([300, 1000], 3, 2, 610, 230) == [300, 390, 610]


def test_dblclick_decision_is_separate_from_embedding_and_no_md_studio_fallback():
    source = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    path = source.split('def preview_bookmark_from_list(', 1)[1].split('def show_browser_preview(',1)[0]
    assert 'external = external_preview_target(row)' in path
    assert "embedded_editor_enabled(" in path
    assert 'launch_external_standalone(external)' in path
    assert 'return True  # Even on failure, never silently open .md in Studio.' in path
    assert path.index('external = external_preview_target(row)') < path.index('studio_preview_target(row, root)')
    assert "target[0].casefold().endswith('.json')" in path
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    assert "embedded_editor_enabled(LAUNCH_HOME, 'studio')" in app


def test_saved_width_is_independent_of_existing_two_column_key():
    source = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    assert "'workspace_files_preview_width'" in source
    assert "'workspace_files_splitter_sizes'" in source
    assert 'self._save_active_preview_width()' in source
    ast.parse(source)


def test_index_and_registered_open_md_also_use_obsidian_not_studio(monkeypatch, tmp_path):
    import external_preview_route
    from file_index import launch_steps, route_registered_open_step
    obsidian = tmp_path / 'Obsidian.exe'
    obsidian.write_text('exe', encoding='utf-8')
    monkeypatch.setattr(external_preview_route, 'find_obsidian_executable', lambda: str(obsidian))
    md = tmp_path / 'outside.md'; md.write_text('# test', encoding='utf-8')
    expected = [{'launch_action_type': 'Run', 'launch_program': str(obsidian),
                 'launch_arguments': [str(md)],
                 'launch_working_directory': str(tmp_path)}]
    assert launch_steps(md, studio_root='C:/Studio') == expected
    step = {'launch_action_type': 'Open', 'launch_target': str(md)}
    assert route_registered_open_step(step, studio_root='C:/Studio') == expected
