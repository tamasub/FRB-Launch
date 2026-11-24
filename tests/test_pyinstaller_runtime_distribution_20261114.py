"""FRB Launch distribution: PyInstaller boot archive must survive ZIP filtering.

Run: python -m unittest tests.test_pyinstaller_runtime_distribution_20261114 -v
"""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_release_package import collect_files, selectable, build
from build_portable_distribution import write_portable
from types import SimpleNamespace


def base_lib(path: Path, *, valid=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('encodings/__init__.pyc' if valid else 'unrelated.txt', b'not executable test fixture')


class PyInstallerRuntimeDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.launch_dist = root / 'launch_dist'
        self.studio = root / 'studio'
        self.source = root / 'source'
        self.node = root / 'node.exe'
        self.license = root / 'LICENSE'
        (self.launch_dist / 'FRBLaunch.exe').parent.mkdir(parents=True)
        (self.launch_dist / 'FRBLaunch.exe').write_bytes(b'launch test executable')
        (self.launch_dist / '_internal' / 'python314.dll').parent.mkdir(parents=True)
        (self.launch_dist / '_internal' / 'python314.dll').write_bytes(b'dll fixture')
        base_lib(self.launch_dist / '_internal/base_library.zip')
        (self.launch_dist / '_internal/old_backup.zip').write_bytes(b'private backup')
        (self.studio / 'NativeShell/_publish').mkdir(parents=True)
        (self.studio / 'NativeShell/_publish/FRBStudio.NativeShell.exe').write_bytes(b'studio exe')
        (self.studio / 'tools/option_settings').mkdir(parents=True)
        (self.studio / 'tools/option_settings/cli.mjs').write_text('console.log("test");', 'utf-8')
        (self.studio / 'tools/change_core').mkdir(parents=True)
        (self.studio / 'tools/change_core/cli.mjs').write_text('// test', 'utf-8')
        enum = self.studio / 'data/json/config/launch_enums_v0_1.json'
        enum.parent.mkdir(parents=True)
        enum.write_text('{}', encoding='utf-8')
        (self.source / 'config').mkdir(parents=True)
        (self.source / 'config/frb_launch_data.json').write_text('{"test":true}', 'utf-8')
        self.node.write_bytes(b'node fixture')
        self.license.write_text('Node.js license fixture', 'utf-8')

    def collect(self):
        return collect_files(self.launch_dist, self.studio, self.source,
                             node_exe=self.node, node_license=self.license)

    def test_pyinstaller_zip_is_included_and_user_zips_excluded(self):
        files = self.collect()
        self.assertIn('_internal/base_library.zip', files)
        self.assertIn('_internal/python314.dll', files)
        self.assertNotIn('_internal/old_backup.zip', files)
        self.assertNotIn('config/frb_launch_data.json', files)

    def test_only_runtime_library_is_exception(self):
        f = self.launch_dist / '_internal/base_library.zip'
        self.assertTrue(selectable(f, '_internal/base_library.zip'))
        self.assertFalse(selectable(f, 'random.zip'))
        self.assertFalse(selectable(f, 'Studio/_internal/base_library.zip'))

    def test_missing_change_core_fails_before_release(self):
        (self.studio / 'tools/change_core/cli.mjs').unlink()
        with self.assertRaisesRegex(ValueError, 'Change Core'):
            self.collect()

    def test_enum_is_included_without_other_config_data(self):
        private = self.studio / 'data/json/config/private.json'
        private.write_text('{}', encoding='utf-8')
        files = self.collect()
        self.assertIn('Studio/data/json/config/launch_enums_v0_1.json', files)
        self.assertNotIn('Studio/data/json/config/private.json', files)

    def test_updater_allows_only_the_system_enum_exception(self):
        from frb_update.contracts import safe_relative, UpdateError
        safe_relative('Studio/data/json/config/launch_enums_v0_1.json')
        with self.assertRaises(UpdateError):
            safe_relative('Studio/data/json/config/private.json')

    def test_missing_enum_blocks_release(self):
        (self.studio / 'data/json/config/launch_enums_v0_1.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Launch Enum JSON missing'):
            self.collect()

    def test_viewdef_reference_missing_blocks_release(self):
        view = self.source / 'defs/launch/menu.json'
        view.parent.mkdir(parents=True)
        view.write_text(json.dumps({'valueVocabularySources': ['config/other.json']}))
        with self.assertRaisesRegex(ValueError, 'vocabulary missing'):
            self.collect()

    def test_missing_library_fails_before_release(self):
        (self.launch_dist / '_internal/base_library.zip').unlink()
        with self.assertRaisesRegex(ValueError, 'base_library.zip'):
            self.collect()

    def test_missing_encodings_fails_before_release(self):
        base_lib(self.launch_dist / '_internal/base_library.zip', valid=False)
        with self.assertRaisesRegex(ValueError, 'encodings'):
            self.collect()

    def test_updater_zip_has_python_runtime_and_manifest_hash(self):
        from frb_update.updater_core import validate_zip
        path = Path(self.temp.name) / 'integrated_update.zip'
        args = SimpleNamespace(
            launch_dist=self.launch_dist, studio_runtime=self.studio,
            launch_source=self.source, output=path, version='0.9.1',
            launch_version='0.9.1', studio_version='0.9.0', notes='',
            archive_url='', node_exe=self.node, node_license=self.license)
        build(args)
        manifest = validate_zip(path)
        self.assertIn('_internal/base_library.zip', manifest['files'])
        self.assertIn('Studio/data/json/config/launch_enums_v0_1.json', manifest['files'])
        with zipfile.ZipFile(path) as z:
            self.assertIn('system/_internal/base_library.zip', z.namelist())
        portable = Path(self.temp.name) / 'integrated_portable.zip'
        updater_exe = Path(self.temp.name) / 'FRBUpdater.exe'
        updater_exe.write_bytes(b'updater fixture')
        write_portable(path, portable, updater_exe, '0.9.1', approved=False)
        with zipfile.ZipFile(portable) as z:
            self.assertIn('FRBLaunch/_internal/base_library.zip', z.namelist())
            self.assertIn('FRBLaunch/Studio/data/json/config/launch_enums_v0_1.json', z.namelist())
            self.assertNotIn('FRBLaunch/_internal/old_backup.zip', z.namelist())
            self.assertIn('FRBLaunch/FRBLaunch.exe', z.namelist())


if __name__ == '__main__':
    unittest.main()
