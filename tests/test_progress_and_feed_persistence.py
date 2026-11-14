"""Regression: completion indicator and update Feed persistence across System upgrades."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from frb_update.progress_ui import bar_display
from frb_update.contracts import UpdateError, read_sources, safe_relative
from frb_update.updater_core import install_zip


def config(updater='file:///tmp/updater.json', product='file:///tmp/product.json'):
    return {'schema': 'frb-update-sources-v1', 'updater_feed_url': updater,
            'product_feed_url': product, 'allow_local_for_test': True}


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')


@pytest.mark.parametrize('phase,cur,total,expected', [
    ('wait', None, None, ('marquee', None)),
    ('verify', 400, 500, ('value', 800)),
    ('stage', 100, 0, ('marquee', None)),
    ('apply', 42, 100, ('value', 420)),
    ('completed', None, None, ('value', 1000)),
    ('completed', 0, 1, ('value', 1000)),
    ('failed', None, None, ('value', 0)),
    ('verify', 102, 100, ('value', 1000)),
])
def test_progress_bar_display(phase, cur, total, expected):
    assert bar_display(phase, cur, total) == expected


def test_native_uses_separate_marquee_and_determinate_bars():
    source = (ROOT / 'src/frb_update/progress_ui.py').read_text('utf-8')
    assert "widgets['bar_marquee'] = child(" in source
    assert "widgets['bar_value'] = child(" in source
    assert "1000 if state['result'] == 0 else 0" in source
    assert "show_window(widgets['bar_marquee'], 0)" in source


def test_sources_legacy_migration_and_updated_system(tmp_path):
    system = tmp_path / 'defs/update/update_sources.json'
    user = tmp_path / 'UserConfig/update_sources.json'
    actual = config()
    dump(system, actual)
    assert read_sources(system, user_path=user) == actual
    assert json.loads(user.read_text('utf-8')) == actual
    # Simulate fresh System template after a product update.
    dump(system, config('', ''))
    assert read_sources(system, user_path=user) == actual


def test_user_config_override_wins(tmp_path):
    system = tmp_path / 'defs/update/update_sources.json'
    user = tmp_path / 'UserConfig/update_sources.json'
    dump(system, config('https://system.example/u', 'https://system.example/p'))
    expect = config('https://user.example/u', 'https://user.example/p')
    dump(user, expect)
    assert read_sources(system, user_path=user) == expect


def test_missing_urls_do_not_create_user_config(tmp_path):
    system = tmp_path / 'defs/update/update_sources.json'
    user = tmp_path / 'UserConfig/update_sources.json'
    dump(system, config('', ''))
    assert read_sources(system, user_path=user)['product_feed_url'] == ''
    assert not user.exists()


def test_corrupt_user_config_rejected_without_fallback(tmp_path):
    system = tmp_path / 'defs/update/update_sources.json'
    user = tmp_path / 'UserConfig/update_sources.json'
    dump(system, config())
    user.parent.mkdir(parents=True)
    user.write_text('bad json', 'utf-8')
    with pytest.raises(UpdateError):
        read_sources(system, user_path=user)


def test_update_manifest_forbids_userconfig():
    with pytest.raises(UpdateError):
        safe_relative('UserConfig/update_sources.json')


def _package(path, version, system_sources):
    items = {'FRBLaunch.exe': b'launcher',
             'Studio/NativeShell/_publish/FRBStudio.NativeShell.exe': b'studio',
             'defs/update/update_sources.json': json.dumps(system_sources).encode()}
    manifest = {'schema': 'frb-system-package-v1',
                'product': 'FRBLaunchIntegrated', 'version': version,
                'components': {'launch': '0.9.1', 'studio': '0.9.0'},
                'files': {name: hashlib.sha256(value).hexdigest()
                          for name, value in items.items()}}
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('release.json', json.dumps(manifest))
        for name, value in items.items():
            archive.writestr('system/' + name, value)


def test_real_updater_preserves_userconfig_and_new_launch_reads_it(tmp_path):
    root = tmp_path / 'FRBLaunch'
    root.mkdir()
    (root / 'FRBLaunch.exe').write_bytes(b'launcher')
    first = tmp_path / '09.zip'
    second = tmp_path / '10.zip'
    _package(first, '0.9.3', config())
    _package(second, '0.9.4', config('', ''))
    install_zip(first, root)
    system = root / 'defs/update/update_sources.json'
    user = root / 'UserConfig/update_sources.json'
    assert read_sources(system, user_path=user)['product_feed_url'] == config()['product_feed_url']
    install_zip(second, root)
    assert json.loads(system.read_text('utf-8'))['product_feed_url'] == ''
    assert read_sources(system, user_path=user)['product_feed_url'] == config()['product_feed_url']
