"""Guard numeric ViewDef vs legacy unlimited-depth JSON at composition boundary."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import file_index
import launch_option_runtime as runtime

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_system_values_are_numeric_and_engine_unlimited():
    for name in ('config/file_index_options.json', 'defaults/file_index_options.json'):
        path = ROOT / name
        assert json.loads(path.read_text(encoding='utf-8'))['max_depth'] == -1
        assert file_index.load_options(path)['max_depth'] is None
    view = json.loads((ROOT / 'defs/launch/options/file_index_options_view_def_v0_1.json').read_text(encoding='utf-8'))
    field = next(f for s in view['views'][0]['sections'] for f in s['fields'] if f['field'] == 'max_depth')
    assert field['type'] == 'number' and field['edit']['min'] == -1


def test_legacy_user_migrates_before_composer_and_preserves_other_values(tmp_path, monkeypatch):
    home = tmp_path / 'launch'
    system = home / 'config/file_index_options.json'
    system.parent.mkdir(parents=True)
    system.write_text('{"max_depth": -1, "search_limit": 100}', encoding='utf-8')
    state = tmp_path / 'state'
    user = state / 'UserConfig/file_index_options.json'
    user.parent.mkdir(parents=True)
    before = b'\xef\xbb\xbf' + json.dumps({'max_depth': None, 'search_limit': 42, 'auto_update': {'check_interval_minutes': 0}, 'exclude_name_contains': ['日本語']}, ensure_ascii=False).encode()
    user.write_bytes(before)
    monkeypatch.setattr(runtime, 'find_studio_root', lambda *a: tmp_path / 'studio')
    monkeypatch.setattr(runtime, 'find_node', lambda *a: 'node')
    def composer(cmd, **kwargs):
        override = json.loads(user.read_text(encoding='utf-8'))
        assert override['max_depth'] == -1
        assert override['search_limit'] == 42
        assert override['auto_update'] == {'check_interval_minutes': 0}
        assert override['exclude_name_contains'] == ['日本語']
        return SimpleNamespace(returncode=0, stdout=json.dumps(override), stderr='')
    # Simulated CLI boundary: the actual Studio Node implementation is external.
    run = Mock(side_effect=composer)
    monkeypatch.setattr(runtime.subprocess, 'run', run)
    out = runtime.effective_options_path(home, state, 'file_index')
    assert run.call_count == 1
    assert file_index.load_options(out)['max_depth'] is None
    assert user.with_name(user.name + '.before_max_depth_v1.bak').read_bytes() == before
    migrated = user.read_bytes()
    assert not runtime.migrate_legacy_file_index_depth(user)
    assert user.read_bytes() == migrated


@pytest.mark.parametrize('raw', [b'{}', b'{"max_depth":0}', b'{"max_depth":4}', b'{"max_depth":-1}', b'{"max_depth":false}', b'{"max_depth":""}', b'broken', b'[]'])
def test_non_null_or_invalid_settings_are_not_rewritten(tmp_path, raw):
    path = tmp_path / 'file_index_options.json'
    path.write_bytes(raw)
    assert not runtime.migrate_legacy_file_index_depth(path)
    assert path.read_bytes() == raw
    assert list(tmp_path.iterdir()) == [path]


def test_missing_user_file_stays_missing(tmp_path):
    path = tmp_path / 'file_index_options.json'
    assert not runtime.migrate_legacy_file_index_depth(path)
    assert not path.exists()
