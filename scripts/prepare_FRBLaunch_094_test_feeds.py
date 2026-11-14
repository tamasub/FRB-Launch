"""PRIVATE_REVIEW: validate 0.9.4 artifacts and stage local test feeds safely.

No update command, package modification, Journal cleanup, or user-data editing.
Windows default paths can be overridden for isolated automated tests.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4
import zipfile

RELEASE = '0.9.4'
LAUNCH = '0.9.2'
STUDIO = '0.9.0'
UPDATER = '0.9.4'
PRODUCT_SCHEMA = 'frb-product-feed-v1'
UPDATER_SCHEMA = 'frb-updater-feed-v1'
SOURCES_SCHEMA = 'frb-update-sources-v1'


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_json(path: Path) -> dict:
    item = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(item, dict):
        raise ValueError('Not a JSON object: ' + str(path))
    return item


def check_test_install(install: Path, expected_versions: set[str]) -> dict:
    install = install.absolute()
    if (install.name.casefold() != 'frblaunch'
            or install.parent.name.casefold() != 'frb_update_test'):
        raise ValueError('Safety guard: expected .../FRB_Update_Test/FRBLaunch: ' + str(install))
    if install.is_symlink() or install.parent.is_symlink():
        raise ValueError('Symlinked test installation is not allowed')
    state_path = install / 'installed_release.json'
    if not (install / 'FRBLaunch.exe').is_file():
        raise FileNotFoundError('Test Launch EXE not found: ' + str(install))
    state = read_json(state_path)
    if state.get('version') not in expected_versions:
        raise ValueError(f'Installed version {state.get("version")} not in {sorted(expected_versions)}')
    expected_launch = {'0.9.3': '0.9.1', '0.9.4': '0.9.2'}[state['version']]
    if state.get('components', {}).get('launch') != expected_launch:
        raise ValueError('Installed Launch component version mismatch: ' + str(state.get('components')))
    backup_root = install.parent / ('.' + install.name + '_update_backups')
    if backup_root.is_dir():
        for journal_path in sorted(backup_root.glob('*/journal.json')):
            phase = read_json(journal_path).get('phase')
            if phase == 'applying':
                raise ValueError('Unrecovered update Journal: ' + str(journal_path))
    return state


def check_build(launch: Path, studio: Path, install: Path) -> None:
    base = launch / 'src'
    app_version = (base / 'app_version.py').read_text(encoding='utf-8-sig')
    if not re.search(r"(?m)^APP_VERSION\s*=\s*['\"]0\.9\.2['\"]\s*$", app_version):
        raise ValueError('src/app_version.py must declare Launch 0.9.2')
    contract = (base / 'frb_update' / 'contracts.py').read_text(encoding='utf-8-sig')
    dialog = (base / 'update_information_dialog.py').read_text(encoding='utf-8-sig')
    progress = (base / 'frb_update' / 'progress_ui.py').read_text(encoding='utf-8-sig')
    if 'user_path=self.user_sources_path' not in dialog or 'def read_sources(path: Path, *, user_path:' not in contract:
        raise ValueError('UserConfig feed persistence changes missing in Launch sources')
    if 'bar_display' not in progress or "if phase == 'completed':" not in progress:
        raise ValueError('Final 100% progress UI change missing from sources')
    if 'source_studio_path' not in (base / 'app.py').read_text(encoding='utf-8-sig'):
        raise ValueError('Studio source selection change missing from src/app.py')
    launch_exe = launch / 'dist' / 'FRBLaunch' / 'FRBLaunch.exe'
    updater_exe = launch / 'dist' / 'updater' / 'FRBUpdater.exe'
    studio_exe = studio / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
    for file in (launch_exe, updater_exe, studio_exe):
        if not file.is_file():
            raise FileNotFoundError('Missing built EXE: ' + str(file))
    required_launch_sources = [base / x for x in (
        'app.py', 'app_version.py', 'source_studio_path.py',
        'update_information_dialog.py', 'frb_update/contracts.py',
        'frb_update/progress_gate.py')]
    required_updater_sources = [base / x for x in (
        'frb_updater_main.py', 'frb_update/progress_ui.py',
        'frb_update/progress_gate.py', 'frb_update/updater_core.py')]
    for exe, source_files, build_command in (
        (launch_exe, required_launch_sources, '_build_windows.bat'),
        (updater_exe, required_updater_sources, '_build_updater_windows.bat'),
    ):
        for source in source_files:
            if exe.stat().st_mtime < source.stat().st_mtime:
                raise ValueError(f'EXE older than {source}; rerun {build_command}')
    if sha256(launch_exe) == sha256(install / 'FRBLaunch.exe'):
        raise ValueError('Built Launch EXE equals installed Launch 0.9.1; stale build likely')
    print('[OK] Source version / patched sources / built EXEs / freshness verified')


def release_files(release_dir: Path) -> tuple[Path, Path, Path]:
    product = release_dir / f'FRBLaunch_{RELEASE}_PRIVATE_REVIEW_update.zip'
    portable = release_dir / f'FRBLaunch_{RELEASE}_PRIVATE_REVIEW_portable.zip'
    updater = release_dir / f'FRBUpdater_{UPDATER}.exe'
    for path in (product, portable, updater):
        if not path.is_file():
            raise FileNotFoundError('Missing immutable release artifact: ' + str(path))
    return product, portable, updater


def validate_release(release_dir: Path, *, launch_source: Path | None = None) -> tuple[Path, Path, Path, dict]:
    product, portable, updater = release_files(release_dir)
    with zipfile.ZipFile(product) as z:
        manifest = json.loads(z.read('release.json'))
        if (manifest.get('schema') != 'frb-system-package-v1'
                or manifest.get('product') != 'FRBLaunchIntegrated'
                or manifest.get('version') != RELEASE
                or manifest.get('components') != {'launch': LAUNCH, 'studio': STUDIO}):
            raise ValueError('Product release.json version/schema/component mismatch')
        entry = z.open('system/FRBLaunch.exe')
        digest = hashlib.sha256()
        with entry:
            for chunk in iter(lambda: entry.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != manifest.get('files', {}).get('FRBLaunch.exe'):
            raise ValueError('Product ZIP Launch EXE does not match its manifest')
        if launch_source is not None:
            built = launch_source / 'dist' / 'FRBLaunch' / 'FRBLaunch.exe'
            if digest.hexdigest() != sha256(built):
                raise ValueError('Product ZIP does not contain newly built Launch EXE')
            if sha256(updater) != sha256(launch_source / 'dist' / 'updater' / 'FRBUpdater.exe'):
                raise ValueError('Staged Updater EXE disagrees with rebuilt Updater')
    with zipfile.ZipFile(portable) as z:
        if ('FRBLaunch/FRBLaunch.exe' not in z.namelist()
                or f'FRBLaunch/updater/versions/{UPDATER}/FRBUpdater.exe' not in z.namelist()):
            raise ValueError('Portable ZIP missing Launch or Updater 0.9.4')
    print('[OK] 0.9.4 immutable ZIPs / versions / Launch / Updater verified')
    return product, portable, updater, manifest


def sources_for(release_dir: Path) -> dict:
    return {'schema': SOURCES_SCHEMA,
            'updater_feed_url': (release_dir / 'updater_feed.json').resolve().as_uri(),
            'product_feed_url': (release_dir / 'product_feed.json').resolve().as_uri(),
            'allow_local_for_test': True}


def atomic_json(path: Path, payload: dict) -> bool:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('Symlink output path refused: ' + str(path))
    contents = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if path.is_file() and path.read_bytes() == contents:
        print('[UNCHANGED]', path)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file():
            raise ValueError('Existing destination is not a file: ' + str(path))
        backup = path.with_name(path.name + '.before_094_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:6] + '.bak')
        with backup.open('xb') as out:
            out.write(path.read_bytes())
            out.flush()
            os.fsync(out.fileno())
        print('[BACKUP]', backup)
    temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as out:
            out.write(contents)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    print('[OK]', path)
    return True


def stage_feeds(release_dir: Path, product: Path, updater: Path, manifest: dict) -> None:
    updater_feed = {'schema': UPDATER_SCHEMA, 'version': UPDATER,
                    'url': updater.resolve().as_uri(), 'size': updater.stat().st_size,
                    'sha256': sha256(updater)}
    product_feed = {'schema': PRODUCT_SCHEMA, 'product': 'FRBLaunchIntegrated',
                    'version': RELEASE, 'components': manifest['components'],
                    'notes': '0.9.4 Exp paths / Studio editor / persisted Feed / 100% progress; PRIVATE REVIEW ONLY',
                    'archive_url': product.resolve().as_uri(),
                    'size': product.stat().st_size, 'sha256': sha256(product)}
    for path, schema in ((release_dir / 'updater_feed.json', UPDATER_SCHEMA),
                         (release_dir / 'product_feed.json', PRODUCT_SCHEMA)):
        if path.exists() and read_json(path).get('schema') != schema:
            raise ValueError('Existing Feed schema mismatch; do not replace: ' + str(path))
    atomic_json(release_dir / 'updater_feed.json', updater_feed)
    atomic_json(release_dir / 'product_feed.json', product_feed)


def check_feeds(release_dir: Path, product: Path, updater: Path) -> None:
    uf = read_json(release_dir / 'updater_feed.json')
    pf = read_json(release_dir / 'product_feed.json')
    if (uf.get('schema'), uf.get('version')) != (UPDATER_SCHEMA, UPDATER):
        raise ValueError('Updater Feed is not 0.9.4')
    if (pf.get('schema'), pf.get('version')) != (PRODUCT_SCHEMA, RELEASE):
        raise ValueError('Product Feed is not 0.9.4')
    if pf.get('components') != {'launch': LAUNCH, 'studio': STUDIO}:
        raise ValueError('Feed component mismatch')
    for feed, file, key in ((uf, updater, 'url'), (pf, product, 'archive_url')):
        if (feed.get('sha256') != sha256(file)
                or feed.get('size') != file.stat().st_size
                or feed.get(key) != file.resolve().as_uri()):
            raise ValueError('Feed SHA-256/size/URL mismatch: ' + str(file))


def configure_test_sources(install: Path, release_dir: Path) -> None:
    sources = sources_for(release_dir)
    paths = (install / 'defs' / 'update' / 'update_sources.json',
             install / 'UserConfig' / 'update_sources.json')
    planned = []
    # Validate all destinations before writing any, and never replace a deliberate
    # non-test URL (for example an official HTTPS production feed).
    for path in paths:
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('Symlink config is not allowed: ' + str(path))
        obj = read_json(path) if path.exists() else {}
        if obj and obj.get('schema') != SOURCES_SCHEMA:
            raise ValueError('Existing config schema mismatch: ' + str(path))
        existing = (obj.get('updater_feed_url') or '', obj.get('product_feed_url') or '')
        wanted = (sources['updater_feed_url'], sources['product_feed_url'])
        if any(value and value != expected for value, expected in zip(existing, wanted)):
            raise ValueError('Non-target Feed URL is configured; manual review required: ' + str(path))
        updated = dict(obj)
        updated.update(sources)
        planned.append((path, updated))
    for path, obj in planned:
        atomic_json(path, obj)
    print('[OK] System and UserConfig local Feed URLs configured (preserved across updates)')


def run(phase: str, launch: Path, studio: Path, release_dir: Path, install: Path) -> None:
    launch, studio, release_dir, install = map(lambda p: Path(p).absolute(),
                                               (launch, studio, release_dir, install))
    state = check_test_install(install, {'0.9.3'} if phase != 'refresh' else {'0.9.3', '0.9.4'})
    if phase == 'preflight':
        check_build(launch, studio, install)
        return
    if phase == 'stage':
        check_build(launch, studio, install)
    product, portable, updater, manifest = validate_release(
        release_dir, launch_source=launch if phase == 'stage' else None)
    if phase == 'stage':
        stage_feeds(release_dir, product, updater, manifest)
    check_feeds(release_dir, product, updater)
    configure_test_sources(install, release_dir)
    print('[SAFE] Update NOT started; installed version remains', state['version'])
    if phase == 'stage':
        print('[NEXT] Test Launch -> Check latest 0.9.4 -> Update ONCE')
    else:
        print('[NEXT] Test Launch -> Check latest; verify current 0.9.4 after install')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('preflight', 'stage', 'refresh'), required=True)
    parser.add_argument('--launch-source', type=Path, default=Path(r'F:\FRB_Apps\FRB_Launch'))
    parser.add_argument('--studio-source', type=Path, default=Path(r'F:\FRB_Apps\FRB_Studio'))
    parser.add_argument('--release-dir', type=Path, default=Path(r'F:\FRB_Apps\FRB_Release_Output'))
    parser.add_argument('--install-root', type=Path, default=Path(r'F:\FRB_Update_Test\FRBLaunch'))
    args = parser.parse_args()
    run(args.phase, args.launch_source, args.studio_source, args.release_dir, args.install_root)


if __name__ == '__main__':
    main()
