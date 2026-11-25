"""Check PySide6's DLL directories survive both release ZIP variants and update.

python -m unittest discover -s tests -p test_pyside6_runtime_dirs_release_20261115.py -v
"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from ensure_qt_runtime_directories import MARKER, ensure_qt_runtime_directories
from build_release_package import collect_files, build
from build_portable_distribution import write_portable
from frb_update.updater_core import install_zip, validate_zip


class QtDirectoryReleaseRegression(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.dist = root / 'dist' / 'FRBLaunch'
        self.source = root / 'source'
        self.studio = root / 'studio'
        self.output = root / 'release.zip'
        self.dist.mkdir(parents=True)
        (self.dist / 'FRBLaunch.exe').write_bytes(b'launch')
        base = self.dist / '_internal'
        base.mkdir()
        (base / 'python314.dll').write_bytes(b'python dll')
        with zipfile.ZipFile(base / 'base_library.zip', 'w') as z:
            z.writestr('encodings/__init__.pyc', b'fixture')
        (base / 'PySide6').mkdir()
        (base / 'PySide6' / 'QtCore.abi3.pyd').write_bytes(b'qt core binary mock')
        (base / 'shiboken6').mkdir()
        (base / 'shiboken6' / 'Shiboken.abi3.pyd').write_bytes(b'shiboken binding mock')
        (self.studio / 'NativeShell/_publish').mkdir(parents=True)
        (self.studio / 'NativeShell/_publish/FRBStudio.NativeShell.exe').write_bytes(b'studio')
        (self.studio / 'tools/option_settings').mkdir(parents=True)
        (self.studio / 'tools/option_settings/cli.mjs').write_text('// test', 'utf-8')
        (self.studio / 'tools/change_core').mkdir(parents=True)
        (self.studio / 'tools/change_core/cli.mjs').write_text('// test', 'utf-8')
        enum = self.studio / 'data/json/config/launch_enums_v0_1.json'
        enum.parent.mkdir(parents=True)
        enum.write_text('{}', encoding='utf-8')
        (self.studio / 'runtime/node').mkdir(parents=True)
        (self.studio / 'runtime/node/node.exe').write_bytes(b'node')
        self.source.mkdir()
        import shutil
        (self.source / 'defaults').mkdir(parents=True, exist_ok=True)
        for name in ('git_commit_options.json', 'file_index_options.json'):
            shutil.copy2(ROOT / 'defaults' / name, self.source / 'defaults' / name)
        self.args = SimpleNamespace(
            launch_dist=self.dist, studio_runtime=self.studio, launch_source=self.source,
            output=self.output, version='0.9.9', launch_version='0.9.9',
            studio_version='0.9.0', notes='', archive_url='',
            node_exe=None, node_license=None,
        )

    def test_missing_directory_marker_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'not protected for release'):
            collect_files(self.dist, self.studio, self.source)
        self.assertFalse(self.output.exists())

    def test_missing_native_module_is_not_hidden_by_empty_directory(self):
        (self.dist / '_internal/shiboken6/Shiboken.abi3.pyd').unlink()
        with self.assertRaisesRegex(ValueError, 'Shiboken.*pyd'):
            ensure_qt_runtime_directories(self.dist, create=True)

    def test_portable_and_updater_preserve_qt_directories(self):
        ensure_qt_runtime_directories(self.dist, create=True)
        files = collect_files(self.dist, self.studio, self.source)
        for rel in ('_internal/shiboken6/libshiboken/' + MARKER,
                    '_internal/PySide6/libpyside/' + MARKER):
            self.assertIn(rel, files)
        build(self.args)
        manifest = validate_zip(self.output)
        for rel in ('_internal/shiboken6/libshiboken/' + MARKER,
                    '_internal/PySide6/libpyside/' + MARKER):
            self.assertIn(rel, manifest['files'])
        portable = self.output.parent / 'portable.zip'
        updater = self.output.parent / 'FRBUpdater.exe'
        updater.write_bytes(b'updater fixture')
        write_portable(self.output, portable, updater, '0.9.9', approved=False)
        with zipfile.ZipFile(portable) as z:
            for rel in ('_internal/shiboken6/libshiboken/' + MARKER,
                        '_internal/PySide6/libpyside/' + MARKER):
                self.assertIn('FRBLaunch/' + rel, z.namelist())
        installed = self.output.parent / 'installed' / 'FRBLaunch'
        installed.mkdir(parents=True)
        (installed / 'FRBLaunch.exe').write_bytes(b'old exe')
        install_zip(self.output, installed, expected_version='0.9.9')
        self.assertTrue((installed / '_internal/shiboken6/libshiboken' / MARKER).is_file())
        self.assertTrue((installed / '_internal/PySide6/libpyside' / MARKER).is_file())

    def test_flat_legacy_layout_is_preserved_too(self):
        base = self.dist
        (base / 'PySide6').mkdir(exist_ok=True)
        (base / 'PySide6/QtCore.abi3.pyd').write_bytes(b'qt')
        (base / 'shiboken6').mkdir(exist_ok=True)
        (base / 'shiboken6/Shiboken.abi3.pyd').write_bytes(b'shiboken')
        ensure_qt_runtime_directories(self.dist, create=True)
        files = collect_files(self.dist, self.studio, self.source)
        self.assertIn('shiboken6/libshiboken/' + MARKER, files)
        self.assertIn('PySide6/libpyside/' + MARKER, files)


if __name__ == '__main__':
    unittest.main()
