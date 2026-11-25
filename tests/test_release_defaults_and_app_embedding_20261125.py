"""Public setting ownership, restart semantics and actual release archive gates."""
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_release_package import build, collect_files, RELEASE_DEFAULT_CONFIGS
from build_portable_distribution import write_portable
from frb_update.updater_core import validate_zip
from launch_state_defaults import ensure_initial_state_ini
import third_column_host_options as hosts
from vscode_guest_bridge import enabled as vscode_enabled
from sakura_guest_bridge import enabled as sakura_enabled
from obsidian_ime_overlay import overlay_enabled


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setenv('FRB_LAUNCH_HOME', str(ROOT))
    monkeypatch.setattr(hosts, '_runtime_state', None)
    monkeypatch.setattr(hosts, '_runtime_values', None)
    for key in hosts._TRIAL_FLAGS.values():
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / 'FRBLaunch'
    path.mkdir()
    return path


def test_public_viewdef_and_system_json_agree():
    base = ROOT / 'defs/launch/options'
    registry = json.loads((base / 'options_registry.json').read_text('utf-8'))
    entry = next(x for x in registry['options'] if x['id'] == 'app_embedding')
    assert entry['caption'] == 'アプリ連携'
    view = json.loads((ROOT / entry['viewDef']).read_text('utf-8'))
    section = view['views'][0]['sections'][0]
    keys = ['embed_' + app for app in hosts.PUBLIC_APPS]
    assert [f['field'] for f in section['fields']] == keys
    assert all(f['type'] == 'boolean' and f['edit']['visible'] for f in section['fields'])
    assert '再起動' in section['caption']
    assert json.loads((ROOT / 'config' / entry['dataFile']).read_text('utf-8')) == dict.fromkeys(keys, True)
    assert 'ensure_app_embedding_user_options(state_dir)' in (ROOT / 'src/option_settings_window.py').read_text('utf-8')
    assert 'initialize_app_embedding_runtime(LAUNCH_HOME)' in (ROOT / 'src/app.py').read_text('utf-8')


def test_migration_preserves_old_ini_and_never_overwrites_saved_user(state):
    ini = state / 'state.ini'
    ini.write_text('[General]\nembed_studio=false\nembed_obsidian=false\nembed_vscode=true\nembed_sakura=false\nappearance_theme=dark\n', encoding='utf-8')
    before = ini.read_bytes()
    user = hosts.ensure_app_embedding_user_options(state)
    assert json.loads(user.read_text('utf-8')) == {'embed_obsidian': False, 'embed_vscode': True, 'embed_sakura': False}
    assert ini.read_bytes() == before
    write_json(user, {'embed_obsidian': True, 'embed_vscode': False, 'embed_sakura': True})
    saved = user.read_bytes()
    assert hosts.ensure_app_embedding_user_options(state) == user
    assert user.read_bytes() == saved and ini.read_bytes() == before
    assert overlay_enabled() and not vscode_enabled() and sakura_enabled()
    assert not hosts.embedded_editor_enabled(ROOT, 'studio')


def test_fresh_install_and_sparse_user_reset_to_system(state):
    ini = state / 'state.ini'
    ensure_initial_state_ini(ROOT / 'defaults/state.ini', ini)
    user = hosts.ensure_app_embedding_user_options(state)
    assert all(json.loads(user.read_text('utf-8')).values())
    ini.write_text('[General]\nembed_studio=false\nembed_vscode=false\nembed_obsidian=false\nembed_sakura=false\n', encoding='utf-8')
    # Sparse override: deleting a field from the User object reverts to System.
    write_json(user, {'embed_vscode': False, 'embed_studio': True})
    assert overlay_enabled() and not vscode_enabled() and sakura_enabled()
    assert not hosts.embedded_editor_enabled(ROOT, 'studio')
    write_json(user, {})
    assert overlay_enabled() and vscode_enabled() and sakura_enabled()


@pytest.mark.parametrize('data', ['broken JSON', '[]', '{"embed_sakura":"true","embed_obsidian":1,"embed_vscode":null}'])
def test_invalid_public_overrides_fail_closed(state, data):
    (state / 'state.ini').write_text('[General]\nembed_sakura=true\nembed_obsidian=true\nembed_vscode=true\nembed_studio=true\n', encoding='utf-8')
    path = state / 'UserConfig' / hosts.OPTION_FILE
    path.parent.mkdir()
    path.write_text(data, encoding='utf-8')
    assert not overlay_enabled() and not vscode_enabled() and not sakura_enabled()
    assert hosts.embedded_editor_enabled(ROOT, 'studio')


def test_saved_change_applies_only_on_restart(state):
    ensure_initial_state_ini(ROOT / 'defaults/state.ini', state / 'state.ini')
    hosts.initialize_app_embedding_runtime(ROOT)
    user = hosts.ensure_app_embedding_user_options(state)
    write_json(user, dict.fromkeys(('embed_' + a for a in hosts.PUBLIC_APPS), False))
    assert overlay_enabled() and vscode_enabled() and sakura_enabled()
    hosts.initialize_app_embedding_runtime(ROOT)
    assert not overlay_enabled() and not vscode_enabled() and not sakura_enabled()


def test_missing_legacy_switches_stay_off_and_trial_guests_preserved(state, monkeypatch):
    (state / 'state.ini').write_text('[General]\nembed_studio=true\n', encoding='utf-8')
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    user = hosts.ensure_app_embedding_user_options(state)
    assert json.loads(user.read_text('utf-8')) == {'embed_obsidian': False, 'embed_vscode': True, 'embed_sakura': True}


@pytest.fixture
def release(tmp_path):
    dist = tmp_path / 'dist'; dist.mkdir()
    (dist / 'FRBLaunch.exe').write_bytes(b'fixture')
    runtime = dist / '_internal/base_library.zip'; runtime.parent.mkdir()
    with zipfile.ZipFile(runtime, 'w') as archive:
        archive.writestr('encodings/__init__.pyc', b'fixture')
    studio = tmp_path / 'studio'
    for name in ('NativeShell/_publish/FRBStudio.NativeShell.exe', 'tools/option_settings/cli.mjs',
                 'tools/change_core/cli.mjs', 'runtime/node/node.exe'):
        path = studio / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'fixture')
    write_json(studio / 'data/json/config/launch_enums_v0_1.json', {})
    source = tmp_path / 'source'
    (source / 'defaults').mkdir(parents=True)
    for name, key in RELEASE_DEFAULT_CONFIGS.items():
        shutil.copy2(ROOT / 'defaults' / name, source / 'defaults' / name)
        write_json(source / 'config' / name, {key: ['PRIVATE_SOURCE']})
        write_json(dist / 'config' / name.upper(), {key: ['PRIVATE_DIST']})
        write_json(dist / 'defaults' / name, {key: ['PRIVATE_DIST_DEFAULT']})
        write_json(source / 'UserConfig' / name, {key: ['PRIVATE_USER']})
    shutil.copy2(ROOT / 'config/app_embedding_options.json', source / 'config')
    return SimpleNamespace(version='0.9.12', launch_version='0.9.12', studio_version='0.9.0',
                           launch_dist=dist, studio_runtime=studio, launch_source=source,
                           output=tmp_path / 'update.zip', notes='', archive_url='')


def test_portable_and_update_use_only_defaults_even_if_source_and_dist_contain_private_settings(release, tmp_path):
    before = {p: p.read_bytes() for p in release.launch_source.rglob('*.json')}
    build(release)
    manifest = validate_zip(release.output)
    updater = tmp_path / 'updater.exe'; updater.write_bytes(b'fixture')
    portable = tmp_path / 'portable.zip'
    write_portable(release.output, portable, updater, '0.9.12', True)
    for name, key in RELEASE_DEFAULT_CONFIGS.items():
        expected = (release.launch_source / 'defaults' / name).read_bytes()
        assert json.loads(expected)[key] == []
        for folder in ('config', 'defaults'):
            rel = folder + '/' + name
            assert rel in manifest['files']
            with zipfile.ZipFile(release.output) as z:
                assert z.read('system/' + rel) == expected
                assert sum(n.casefold() == ('system/' + rel).casefold() for n in z.namelist()) == 1
                assert not any('/UserConfig/' in n for n in z.namelist())
            with zipfile.ZipFile(portable) as z:
                assert z.read('FRBLaunch/' + rel) == expected
    assert json.loads((release.launch_source / 'defaults/file_index_options.json').read_text('utf-8'))['auto_update']['max_scan_workers'] == 2
    assert before == {p: p.read_bytes() for p in release.launch_source.rglob('*.json')}


@pytest.mark.parametrize('name', list(RELEASE_DEFAULT_CONFIGS))
@pytest.mark.parametrize('failure', ['missing', 'private', 'invalid'])
def test_missing_or_unsafe_defaults_block_release_no_fallback(release, name, failure):
    path = release.launch_source / 'defaults' / name
    if failure == 'missing': path.unlink()
    elif failure == 'private': write_json(path, {RELEASE_DEFAULT_CONFIGS[name]: ['PRIVATE']})
    else: path.write_text('not JSON', encoding='utf-8')
    with pytest.raises(ValueError, match='配布用標準設定'):
        build(release)
    assert not release.output.exists()
