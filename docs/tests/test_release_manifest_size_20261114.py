"""Regression tests for full-size FRB Launch/Studio release manifests.

A realistic PyInstaller/.NET distribution can have thousands of artifacts.
The release inventory is intentionally readable JSON, but must stay bounded.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))

from frb_update.contracts import UpdateError
from frb_update.updater_core import MAX_RELEASE_MANIFEST_SIZE, validate_zip
import frb_update.updater_core as updater_core
from build_release_package import build


def _dummy_app_parts(tmp_path):
    launch = tmp_path/'launch_dist'
    launch.mkdir()
    (launch/'FRBLaunch.exe').write_bytes(b'launch')
    # PyInstaller onedir's Python runtime cannot start without this archive.
    base_lib = launch/'_internal'/'base_library.zip'
    base_lib.parent.mkdir(parents=True)
    with zipfile.ZipFile(base_lib, 'w') as z:
        z.writestr('encodings/__init__.pyc', b'fixture')
    studio = tmp_path/'studio'
    studio_exe = studio/'NativeShell'/'_publish'/'FRBStudio.NativeShell.exe'
    studio_exe.parent.mkdir(parents=True)
    studio_exe.write_bytes(b'studio')
    cli = studio/'tools'/'option_settings'/'cli.mjs'
    cli.parent.mkdir(parents=True)
    cli.write_text('', 'utf-8')
    node = studio/'runtime'/'node'/'node.exe'
    node.parent.mkdir(parents=True)
    node.write_bytes(b'node')
    source = tmp_path/'launch_source'
    source.mkdir()
    return SimpleNamespace(
        version='0.9.0', launch_version='0.9.0', studio_version='0.9.0',
        launch_dist=launch, studio_runtime=studio, launch_source=source,
        output=tmp_path/'release.zip', notes='', archive_url='',
    )


def test_large_manifest_over_old_512k_limit_is_valid(tmp_path):
    # Over 512 KiB of inventory, but safely under the new bounded limit.
    core = {
        'FRBLaunch.exe': b'L',
        'Studio/NativeShell/_publish/FRBStudio.NativeShell.exe': b'S',
    }
    core.update({f'Studio/wwwroot/assets/pkg_{i:05d}.dll': b'X' for i in range(6000)})
    manifest = {
        'schema': 'frb-system-package-v1', 'product': 'FRBLaunchIntegrated',
        'version': '0.9.0', 'components': {'launch': '0.9.0', 'studio': '0.9.0'},
        'notes': '',
        'files': {name: hashlib.sha256(blob).hexdigest() for name, blob in core.items()},
    }
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    assert 512 * 1024 < len(encoded) < MAX_RELEASE_MANIFEST_SIZE
    archive = tmp_path/'large_update.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('release.json', encoded)
        for name, blob in core.items():
            z.writestr('system/'+name, blob)
    result = validate_zip(archive)
    assert len(result['files']) == len(core)


def test_manifest_limit_is_still_enforced(tmp_path):
    archive = tmp_path/'oversized_update.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('release.json', b' ' * (MAX_RELEASE_MANIFEST_SIZE + 1))
    with pytest.raises(UpdateError, match='release.jsonが大きすぎます'):
        validate_zip(archive)


def test_failed_validation_does_not_leave_incomplete_release(tmp_path, monkeypatch):
    args = _dummy_app_parts(tmp_path)

    def reject_release(*args, **kwargs):
        raise UpdateError('simulated verification failure')

    monkeypatch.setattr(updater_core, 'validate_zip', reject_release)
    with pytest.raises(UpdateError, match='simulated verification failure'):
        build(args)
    assert not args.output.exists()
    assert not list(tmp_path.glob('*.building'))


def test_successful_build_does_not_overwrite_existing_release(tmp_path):
    args = _dummy_app_parts(tmp_path)
    build(args)
    assert validate_zip(args.output)['version'] == args.version
    original = args.output.read_bytes()
    with pytest.raises(FileExistsError):
        build(args)
    assert args.output.read_bytes() == original
