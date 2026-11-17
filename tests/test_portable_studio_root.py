# Standalone tests: no PySide6 required.
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from runtime_paths import bundled_studio_root

class PortableStudioRootTests(unittest.TestCase):
    def test_moving_bundle_keeps_studio_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'Folder With Space'
            exe = root / 'Studio' / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b'test')
            other = Path(tmp) / 'other'
            other.mkdir()
            with patch('os.getcwd', return_value=str(other)):
                self.assertEqual(bundled_studio_root(root), str((root / 'Studio').resolve()))
            moved = Path(tmp) / 'moved'
            root.rename(moved)
            self.assertEqual(bundled_studio_root(moved), str((moved / 'Studio').resolve()))

    def test_frb_apps_sibling_with_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps = Path(tmp) / 'FRB_Apps'
            launch = apps / 'FRB_Launch'
            launch.mkdir(parents=True)
            studio = apps / 'FRB_Studio'
            exe = studio / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b'test')
            self.assertEqual(bundled_studio_root(launch), str(studio.resolve()))

    def test_frb_apps_sibling_with_source_but_without_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps = Path(tmp) / 'FRB_Apps'
            launch = apps / 'FRB_Launch'
            launch.mkdir(parents=True)
            studio = apps / 'FRB_Studio'
            project = studio / 'NativeShell' / 'FRBStudio.NativeShell.csproj'
            project.parent.mkdir(parents=True)
            project.write_text('<Project/>', encoding='utf-8')
            # Missing native build must be diagnosed at the NEW path.
            self.assertEqual(bundled_studio_root(launch), str(studio.resolve()))

    def test_portable_bundle_takes_priority_over_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Path(tmp) / 'FRB_Apps' / 'FRB_Launch'
            bundled = launch / 'Studio'
            sibling = launch.parent / 'FRB_Studio'
            for folder in (bundled, sibling):
                exe = folder / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
                exe.parent.mkdir(parents=True)
                exe.write_bytes(b'test')
            self.assertEqual(bundled_studio_root(launch), str(bundled.resolve()))

    def test_runnable_sibling_beats_incomplete_portable_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Path(tmp) / 'FRB_Apps' / 'FRB_Launch'
            project = launch / 'Studio' / 'NativeShell' / 'FRBStudio.NativeShell.csproj'
            project.parent.mkdir(parents=True)
            project.write_text('<Project/>', encoding='utf-8')
            sibling = launch.parent / 'FRB_Studio'
            exe = sibling / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b'test')
            self.assertEqual(bundled_studio_root(launch), str(sibling.resolve()))

    def test_without_bundled_studio_keeps_developer_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Path(tmp) / 'FRB_Apps' / 'FRB_Launch'
            launch.mkdir(parents=True)
            # An arbitrary directory with the right name is not a valid Studio.
            (launch.parent / 'FRB_Studio').mkdir()
            self.assertIsNone(bundled_studio_root(launch))

if __name__ == '__main__':
    unittest.main()
