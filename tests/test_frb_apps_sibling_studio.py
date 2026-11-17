"""Pure-Python tests for the FRB_Apps sibling Studio migration."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from launch_menu_registration import studio_core_root
from runtime_paths import bundled_studio_root


class SiblingStudioCoreTests(unittest.TestCase):
    def test_studio_core_uses_sibling_even_if_configured_root_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps = Path(tmp) / 'FRB_Apps'
            launch = apps / 'FRB_Launch'
            launch.mkdir(parents=True)
            studio = apps / 'FRB_Studio'
            cli = studio / 'tools/change_core/cli.mjs'
            viewdef = launch / 'defs/launch/frb_launch_maintenance_view_def_v0_1.json'
            for path in (cli, viewdef):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('test', encoding='utf-8')
            old = Path(tmp) / 'FRB/tools/FRBStudio_App'
            old_cli = old / 'tools/change_core/cli.mjs'
            old_view = old / 'defs/launch/frb_launch_maintenance_view_def_v0_1.json'
            for path in (old_cli, old_view):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('test', encoding='utf-8')
            self.assertEqual(studio_core_root(launch, old), studio.resolve())
            # Studio owns no Launch ViewDef; renaming Studio's defs/launch is safe.
            self.assertFalse((studio / 'defs/launch').exists())

    def test_new_root_is_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps = Path(tmp) / 'FRB_Apps'
            launch = apps / 'FRB_Launch'
            launch.mkdir(parents=True)
            studio = apps / 'FRB_Studio'
            project = studio / 'NativeShell/FRBStudio.NativeShell.csproj'
            project.parent.mkdir(parents=True)
            project.write_text('test', encoding='utf-8')
            self.assertEqual(bundled_studio_root(launch), str(studio.resolve()))

if __name__ == '__main__': unittest.main()
