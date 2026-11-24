"""The release GUI's shared system inventory includes Launch-root README files."""
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from build_release_package import build
from build_portable_distribution import write_portable
from frb_update.updater_core import validate_zip


def _release_fixture(tmp_path):
    launch_dist = tmp_path / 'dist' / 'FRBLaunch'
    launch_dist.mkdir(parents=True)
    (launch_dist / 'FRBLaunch.exe').write_bytes(b'launch')
    base_library = launch_dist / '_internal' / 'base_library.zip'
    base_library.parent.mkdir()
    with zipfile.ZipFile(base_library, 'w') as archive:
        archive.writestr('encodings/__init__.pyc', b'fixture')

    studio = tmp_path / 'studio'
    for name in ('NativeShell/_publish/FRBStudio.NativeShell.exe',
                 'tools/option_settings/cli.mjs', 'tools/change_core/cli.mjs', 'runtime/node/node.exe'):
        path = studio / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')

    enum = studio / 'data/json/config/launch_enums_v0_1.json'
    enum.parent.mkdir(parents=True)
    enum.write_text('{}', encoding='utf-8')
    source = tmp_path / 'FRB_Launch'
    source.mkdir()
    (source / 'README.md').write_text('# Launch README\n', encoding='utf-8')
    (source / 'README_Vector_v0.9.11.txt').write_text('ベクター向け説明\n', encoding='utf-8')
    (source / 'ReadMe_INSTALL.TXT').write_text('Install instructions\n', encoding='utf-8')
    (source / 'notes.txt').write_text('Do not distribute this\n', encoding='utf-8')
    (source / 'README_backup.zip').write_bytes(b'do not ship arbitrary ZIPs')
    docs = source / 'docs'
    docs.mkdir()
    (docs / 'README_NOT_ROOT.md').write_text('not a root file\n', encoding='utf-8')

    return SimpleNamespace(
        version='0.9.12', launch_version='0.9.12', studio_version='0.9.0',
        launch_dist=launch_dist, studio_runtime=studio, launch_source=source,
        output=tmp_path / 'release_update.zip', notes='', archive_url='',
    )


def test_root_readmes_are_in_update_and_portable_at_top_level(tmp_path):
    args = _release_fixture(tmp_path)
    build(args)
    manifest = validate_zip(args.output, expected_version=args.version)
    expected = ('README.md', 'README_Vector_v0.9.11.txt', 'ReadMe_INSTALL.TXT')
    for name in expected:
        assert name in manifest['files']
    for name in ('notes.txt', 'README_backup.zip', 'docs/README_NOT_ROOT.md'):
        assert name not in manifest['files']
    with zipfile.ZipFile(args.output) as archive:
        for name in expected:
            assert archive.read('system/' + name) == (args.launch_source / name).read_bytes()

    portable = tmp_path / 'release_portable.zip'
    updater = tmp_path / 'FRBUpdater.exe'
    updater.write_bytes(b'updater')
    write_portable(args.output, portable, updater, '0.9.12', True)
    with zipfile.ZipFile(portable) as archive:
        for name in expected:
            assert archive.read('FRBLaunch/' + name) == (args.launch_source / name).read_bytes()
        assert 'FRBLaunch/README_backup.zip' not in archive.namelist()
        assert 'FRBLaunch/docs/README_NOT_ROOT.md' not in archive.namelist()


def test_gui_release_stages_through_shared_inventory():
    gui = (ROOT / '_release_FRBLaunch_GUI.ps1').read_text('utf-8-sig')
    pipeline = (ROOT / 'release_FRBLaunch_GitHub.ps1').read_text('utf-8-sig')
    stage = (ROOT / 'scripts/release_github_pipeline.py').read_text('utf-8-sig')
    portable = (ROOT / 'scripts/build_portable_distribution.py').read_text('utf-8-sig')
    assert 'release_FRBLaunch_GitHub.ps1' in gui
    assert "Invoke-ReleaseStep 'stage' @()" in pipeline
    assert 'build_portable_distribution.py' in stage
    assert 'build_update_zip(args_release)' in portable
