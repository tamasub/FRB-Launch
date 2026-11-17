"""Focused acceptance tests for the optional Obsidian / Sakura trial.

Cross-process HWND attachment and Ctrl+S persistence must still be checked on
Windows with real installations; they cannot be asserted by Linux unit tests.
"""
from pathlib import Path
import ast
from types import SimpleNamespace

from external_preview_route import (ExternalPreviewTarget, external_preview_target,
                                    external_start_command, find_vault_root,
                                    obsidian_open_uri, find_sakura_executable)
from external_win32_host import find_new_editor_window


SRC = Path(__file__).resolve().parents[1] / 'src'


def create_documents(tmp_path):
    vault = tmp_path / 'FRB Notes'
    vault.mkdir()
    (vault / '.obsidian').mkdir()
    nested = vault / 'FRB Experiment'
    nested.mkdir()
    md = nested / '釣り メモ.md'
    md.write_text('# FRB\n', encoding='utf-8')
    txt = nested / 'my notes.txt'
    txt.write_text('test\n', encoding='utf-8')
    ini = nested / 'state.ini'
    ini.write_text('[style]\n', encoding='utf-8')
    outside = tmp_path / 'outside.md'
    outside.write_text('outside\n', encoding='utf-8')
    json = nested / 'config.json'
    json.write_text('{}', encoding='utf-8')
    exe = tmp_path / 'sakura.exe'
    exe.write_bytes(b'exe-test')
    return md, txt, ini, outside, json, exe


def test_md_in_a_vault_routes_to_obsidian(tmp_path):
    md, *_ = create_documents(tmp_path)
    lookup = lambda path: find_vault_root(path, registered_roots=[md.parents[1]])
    result = external_preview_target({'_browse_file': str(md)}, vault_lookup=lookup)
    assert result == ExternalPreviewTarget('obsidian', str(md))
    assert find_vault_root(md, registered_roots=[md.parents[1]]) == md.parents[1]


def test_md_outside_vault_routes_to_obsidian(tmp_path):
    _, _, _, outside, *_ = create_documents(tmp_path)
    assert external_preview_target({'_browse_file': str(outside)}).app == 'obsidian'


def test_txt_and_ini_route_only_to_real_sakura(tmp_path):
    _, txt, ini, _, _, exe = create_documents(tmp_path)
    for file in (txt, ini):
        route = external_preview_target({'_indexed_file': str(file)},
                                        sakura_lookup=lambda: str(exe))
        assert route == ExternalPreviewTarget('sakura', str(file), str(exe))
        assert external_start_command(route) == [str(exe), '--', str(file)]


def test_missing_sakura_no_interception(tmp_path):
    _, txt, ini, *_ = create_documents(tmp_path)
    assert external_preview_target({'_browse_file': str(txt)}, sakura_lookup=lambda: None) is None
    assert external_preview_target({'_browse_file': str(ini)}, sakura_lookup=lambda: None) is None


def test_no_json_or_other_extension_interception(tmp_path):
    md, _, _, _, json, _ = create_documents(tmp_path)
    assert external_preview_target({'_browse_file': str(json)}) is None
    assert external_preview_target({'_browse_file': str(md.with_suffix('.none'))}) is None


def test_only_real_files_list_leaves(tmp_path):
    md, *_ = create_documents(tmp_path)
    assert external_preview_target({'title': str(md)}) is None
    assert external_preview_target({'_browse_file': str(md.parent)}) is None
    assert external_preview_target({'_browse_file': str(md),
                                    '_launch_virtual_node': {'kind': 'file'}}) is None
    assert external_preview_target({'_browse_file': str(md),
                                    '_launch_virtual_node': {'kind': 'folder'}}) is None


def test_uppercase_file_suffix(tmp_path):
    md, _, _, _, _, exe = create_documents(tmp_path)
    upper = md.with_suffix('.MD')
    upper.write_text('# upper', encoding='utf-8')
    lookup = lambda path: find_vault_root(path, registered_roots=[md.parents[1]])
    assert external_preview_target({'_file': str(upper)}, vault_lookup=lookup).app == 'obsidian'
    upper_txt = md.with_suffix('.TXT')
    upper_txt.write_text('upper', encoding='utf-8')
    assert external_preview_target({'_file': str(upper_txt)},
                                   sakura_lookup=lambda: str(exe)).app == 'sakura'


def test_obsidian_uri_encodes_unicode_spaces_and_windows_path():
    uri = obsidian_open_uri(r'F:\FRB\note vault\釣りと FFT.md')
    assert uri.startswith('obsidian://open?path=F%3A%5CFRB%5C')
    assert '%20' in uri and '%E9%87%A3' in uri
    assert uri.endswith('&paneType=window')


def test_obsidian_uri_is_not_sakura_command():
    import pytest
    with pytest.raises(ValueError):
        external_start_command(ExternalPreviewTarget('obsidian', r'C:\vault\a.md'))


def test_external_routes_are_side_effect_free(tmp_path):
    md, txt, ini, _, _, exe = create_documents(tmp_path)
    files = [md, txt, ini]
    before = [p.read_bytes() for p in files]
    for p in files:
        external_preview_target({'_browse_file': str(p)}, sakura_lookup=lambda: str(exe))
    assert before == [p.read_bytes() for p in files]


def test_sakura_env_override_uses_real_exe_and_never_shell(monkeypatch, tmp_path):
    exe = tmp_path / 'sakura.exe'
    exe.write_bytes(b'exe-test')
    monkeypatch.setenv('FRB_LAUNCH_SAKURA_EXE', str(exe))
    assert find_sakura_executable() == str(exe)
    monkeypatch.setenv('FRB_LAUNCH_SAKURA_EXE', 'fake.exe & del files')
    assert find_sakura_executable() is None


def test_new_obsidian_popup_only_not_existing_window(monkeypatch):
    import external_win32_host as host
    target = ExternalPreviewTarget('obsidian', 'C:/vault/Note.md')
    monkeypatch.setattr(host, 'editor_windows', lambda app: [
        (100, 50, 'Note - Obsidian'),  # existing, must never be stolen
        (200, 50, 'Note - Obsidian'),  # new pop-out
    ])
    assert find_new_editor_window(target, {100}) == 200
    assert find_new_editor_window(target, {100, 200}) is None


def test_sakura_target_hwnd_rejects_existing(monkeypatch):
    import external_win32_host as host
    target = ExternalPreviewTarget('sakura', 'C:/work/state.ini', 'C:/sakura.exe')
    monkeypatch.setattr(host, 'editor_windows', lambda app: [
        (200, 31, 'state.ini - Sakura Editor'),
    ])
    assert find_new_editor_window(target, {200}, launched_pid=31) is None
    assert find_new_editor_window(target, set(), launched_pid=31) == 200


def test_sakura_new_pid_fallback_only_when_unambiguous(monkeypatch):
    import external_win32_host as host
    target = ExternalPreviewTarget('sakura', 'C:/work/f.ini', 'C:/sakura.exe')
    monkeypatch.setattr(host, 'editor_windows', lambda app: [
        (200, 31, 'Modified - Sakura Editor'),
        (300, 32, 'Different - Sakura Editor'),
    ])
    assert find_new_editor_window(target, set(), launched_pid=31) == 200
    assert find_new_editor_window(target, set(), launched_pid=55) is None


def test_title_collision_ambiguous_refused(monkeypatch):
    import external_win32_host as host
    target = ExternalPreviewTarget('obsidian', 'C:/vault/Note.md')
    monkeypatch.setattr(host, 'editor_windows', lambda app: [
        (200, 50, 'Note - Obsidian'),
        (300, 51, 'Note - Obsidian'),
    ])
    assert find_new_editor_window(target, set()) is None


def test_target_key_is_stable_for_windows_case():
    assert ExternalPreviewTarget('sakura', 'C:/FRB/A.ini').key == \
           ExternalPreviewTarget('sakura', 'c:/frb/a.ini').key


def test_ui_routes_only_doubleclick_and_keeps_json():
    expanded = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    segment = expanded.split('def preview_bookmark_from_list(', 1)[1].split('def show_browser_preview(', 1)[0]
    assert 'external_preview_target(row)' in segment
    assert 'show_external_preview(external)' in segment
    assert segment.index('external_preview_target(row)') < segment.index('studio_preview_target(row, root)')
    assert 'embedded_editor_enabled(' in segment and 'launch_external_standalone(external)' in segment
    assert 'preview_authored_launch_url' in segment
    assert 'return self.show_studio_preview(target)' in segment


def test_ui_reuses_existing_host_and_retains_saves():
    panel = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
    view = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    assert 'AttachedStudioWindow' in panel
    assert 'self._external_parked[self._external_key] = attached.hwnd' in panel
    assert 'attached.detach(foreground=False, show_window=False)' in panel
    assert 'self._external_timer.stop()' in panel
    assert 'restore_parked_studio_window(hwnd)' in panel
    assert 'panel.hide()' in view
    assert '.kill(' not in panel and '.terminate(' not in panel
    assert 'release_studio_preview()' in (SRC / 'app.py').read_text(encoding='utf-8')


def test_window_discovery_restricts_program_and_titled_popup():
    source = (SRC / 'external_win32_host.py').read_text(encoding='utf-8')
    assert "'obsidian.exe'" in source
    assert "'sakura.exe'" in source
    assert 'hwnd not in previous' in source
    assert 'if len(titled) == 1:' in source
    assert 'GetWindowThreadProcessId' in source


def test_while_external_window_launches_launcher_remains_visible():
    source = (SRC / 'app.py').read_text(encoding='utf-8')
    app_state = source.split('    def app_state(self, state):', 1)[1].split('    def page_key(', 1)[0]
    outside = source.split('    def dismiss_from_outside_click():', 1)[1].split('    try:\n        desktop_click', 1)[0]
    assert 'external_embedding_pending' in app_state
    assert 'external_embedding_pending' in outside
    assert 'external_embedding_pending' in (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
