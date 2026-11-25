"""One-time state.ini seed contract: user data always wins."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from launch_state_defaults import ensure_initial_state_ini


def test_seed_known_menu_settings_from_general_section(tmp_path):
    source = tmp_path / 'system/defaults/state.ini'
    source.parent.mkdir(parents=True)
    source.write_text('[General]\nappearance_theme=Light\nvdi_no_cursor_warp=off\n'
                      'folder_open_mode=double\nexperiment_mouse_pointer_rod_windows=1\n'
                      'window_geometry=unexpected\npage=something\n', encoding='utf-8')
    destination = tmp_path / 'appdata/FRBLaunch/state.ini'
    assert ensure_initial_state_ini(source, destination) == destination
    content = destination.read_text(encoding='utf-8')
    assert content.startswith('[General]\n')
    assert 'appearance_theme=light\n' in content
    assert 'vdi_no_cursor_warp=false\n' in content
    assert 'folder_open_mode=double\n' in content
    assert 'experiment_mouse_pointer_rod_windows=true\n' in content
    assert 'window_geometry' not in content
    assert 'page=' not in content
    # Missing settings are not written: their current app.py fallbacks apply.
    assert 'dismiss_on_outside_click=' not in content
    assert 'experiment_remote_15_column=' not in content


def test_existing_state_bytes_untouched_even_if_template_changes(tmp_path):
    source = tmp_path / 'defaults/state.ini'
    source.parent.mkdir()
    source.write_text('[General]\nappearance_theme=light\n', encoding='utf-8')
    destination = tmp_path / 'appdata/state.ini'
    destination.parent.mkdir()
    raw = b'[General]\r\nappearance_theme=dark\r\nlast_current=keep\r\n'
    destination.write_bytes(raw)
    assert ensure_initial_state_ini(source, destination) == destination
    source.write_text('[General]\nappearance_theme=dark\n', encoding='utf-8')
    assert ensure_initial_state_ini(source, destination) == destination
    assert destination.read_bytes() == raw


def test_missing_template_creates_empty_general_and_uses_application_fallback(tmp_path):
    target = tmp_path / 'user/state.ini'
    ensure_initial_state_ini(tmp_path / 'defaults/absent.ini', target)
    assert target.read_text(encoding='utf-8') == '[General]\n'


def test_invalid_values_are_ignored_instead_of_changing_system_defaults(tmp_path):
    source = tmp_path / 'defaults/state.ini'
    source.parent.mkdir()
    source.write_text('[General]\nappearance_theme=purple\n'
                      'vdi_no_cursor_warp=maybe\nfolder_open_mode=bogus\n'
                      'desktop_remote_enabled=yes\n', encoding='utf-8')
    target = tmp_path / 'user/state.ini'
    ensure_initial_state_ini(source, target)
    assert target.read_text(encoding='utf-8') == '[General]\ndesktop_remote_enabled=true\n'


def test_malformed_template_falls_back_and_existing_directory_is_not_replaced(tmp_path):
    source = tmp_path / 'defaults/state.ini'
    source.parent.mkdir()
    source.write_text('invalid no section', encoding='utf-8')
    target = tmp_path / 'user/state.ini'
    ensure_initial_state_ini(source, target)
    assert target.read_text(encoding='utf-8') == '[General]\n'
    folder_target = tmp_path / 'dir_as_state.ini'
    folder_target.mkdir()
    try:
        ensure_initial_state_ini(source, folder_target)
        assert False, 'expected RuntimeError'
    except RuntimeError:
        pass


def test_shipped_template_and_startup_hook_and_package_source():
    destination = ROOT / 'defaults/state.ini'
    assert destination.is_file()
    text = destination.read_text(encoding='utf-8')
    for key in ('appearance_theme', 'vdi_no_cursor_warp', 'dismiss_on_outside_click',
                'folder_open_mode', 'desktop_remote_enabled', 'remote_display_mode',
                'experiment_mouse_pointer_rod',
                'experiment_mouse_pointer_rod_windows', 'experiment_mouse_pointer_rod_smart'):
        assert key + '=' in text
    source = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    assert "ensure_initial_state_ini(LAUNCH_HOME / 'defaults' / 'state.ini', STATE / 'state.ini')" in source
    assert source.index('    ensure_initial_state_ini(') < source.index('    window=Launcher()')
    package = (ROOT / 'scripts/build_release_package.py').read_text(encoding='utf-8')
    assert "('defs','defaults','scripts','config')" in package


def test_app_host_switches_include_sakura_default_on_and_user_state_wins(tmp_path):
    shipped = ROOT / 'defaults/state.ini'
    text = shipped.read_text(encoding='utf-8')
    for key in ('embed_studio', 'embed_obsidian', 'embed_vscode'):
        assert f'{key}=true' in text
    assert 'embed_sakura=true' in text

    first = tmp_path / 'first/state.ini'
    ensure_initial_state_ini(shipped, first)
    first_text = first.read_text(encoding='utf-8')
    for key in ('embed_studio', 'embed_obsidian', 'embed_vscode'):
        assert f'{key}=true' in first_text
    assert 'embed_sakura=true' in first_text

    template = tmp_path / 'defaults/state.ini'
    template.parent.mkdir(parents=True)
    template.write_text('[General]\nembed_studio=yes\nembed_obsidian=no\n'
                        'embed_sakura=bogus\n', encoding='utf-8')
    second = tmp_path / 'second/state.ini'
    ensure_initial_state_ini(template, second)
    assert second.read_text(encoding='utf-8') == ('[General]\nembed_studio=true\n'
                                                       'embed_obsidian=false\n')
    original = second.read_bytes()
    template.write_text('[General]\nembed_studio=false\n', encoding='utf-8')
    ensure_initial_state_ini(template, second)
    assert second.read_bytes() == original
