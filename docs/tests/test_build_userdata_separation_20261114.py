"""Build cannot require the old Launch config or mutate UserData."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from prepare_launch_home import check_build_template


class BuildUserDataSeparationTests(unittest.TestCase):
    def test_repo_build_uses_template_even_when_legacy_config_missing(self):
        self.assertFalse((ROOT / 'config/frb_launch_data.json').exists())
        assert check_build_template(ROOT) == ROOT / 'defaults/frb_launch_data.template.json'

    def test_check_template_does_not_touch_config_or_existing_userdata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'defaults').mkdir()
            (root / 'config').mkdir()
            template = root / 'defaults/frb_launch_data.template.json'
            template.write_bytes((ROOT / 'defaults/frb_launch_data.template.json').read_bytes())
            user = root / 'LocalAppData/FRBLaunch/UserData/frb_launch_data.json'
            user.parent.mkdir(parents=True)
            user.write_text('{"title":"user-owned"}', encoding='utf-8')
            before_user = user.read_bytes()
            before_template = template.read_bytes()
            self.assertEqual(check_build_template(root), template)
            self.assertEqual(check_build_template(root), template)
            self.assertEqual(user.read_bytes(), before_user)
            self.assertEqual(template.read_bytes(), before_template)
            self.assertFalse((root / 'config/frb_launch_data.json').exists())

    def test_invalid_template_does_not_create_legacy_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            template = root / 'defaults/frb_launch_data.template.json'
            template.parent.mkdir()
            template.write_bytes(b'{invalid')
            with self.assertRaises(RuntimeError):
                check_build_template(root)
            self.assertFalse((root / 'config').exists())

    def test_build_bat_uses_read_only_build_check(self):
        bat=(ROOT/'_build_windows.bat').read_text(encoding='utf-8')
        self.assertIn(r'src\prepare_launch_home.py --build',bat)
        self.assertNotIn(r'src\prepare_launch_home.py' + '\nif errorlevel 1',bat)
        self.assertLess(bat.index(r'src\prepare_launch_home.py --build'),
                        bat.index(r'src\build_output_preflight.py'))

if __name__ == '__main__':
    unittest.main()
