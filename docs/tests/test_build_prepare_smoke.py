"""Exercise the exact CLI pre-build step without modifying user files."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]

class BuildPrepareSmokeTests(unittest.TestCase):
    def test_build_template_without_legacy_config_or_user_modifications(self):
        # Exact CLI used by _build_windows.bat, without requiring config/frb_launch_data.json.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config').mkdir()
            (root / 'defaults').mkdir()
            shutil.copy2(SOURCE / 'defaults/frb_launch_data.template.json',
                         root / 'defaults/frb_launch_data.template.json')
            (root / 'src').mkdir()
            for source in (SOURCE / 'src').glob('*.py'):
                shutil.copy2(source, root / 'src' / source.name)
            ready = root / '.launch_home_ready'
            ready.write_text('old marker must not influence build', encoding='utf-8')
            # A template is only read, never rewritten, even on repeated builds.
            template = root / 'defaults/frb_launch_data.template.json'
            original = template.read_bytes()
            cmd = [sys.executable, str(root / 'src' / 'prepare_launch_home.py'), '--build']
            for _ in range(2):
                result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('template validated', result.stdout)
                self.assertEqual(template.read_bytes(), original)
                self.assertFalse((root / 'config/frb_launch_data.json').exists())
                self.assertEqual(ready.read_text(encoding='utf-8'),
                                 'old marker must not influence build')
            linked = subprocess.run([sys.executable, str(root / 'src' / 'prepare_launch_home.py'), '--link'],
                                    cwd=root, capture_output=True, text=True)
            self.assertEqual(linked.returncode, 0, linked.stdout + linked.stderr)
            link = json.loads((root / 'dist/FRBLaunch/launch_home.json').read_text())
            self.assertEqual(link['launch_home'], '../..')

    def test_missing_template_stops_build_before_packaging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'src').mkdir()
            for source in (SOURCE / 'src').glob('*.py'):
                shutil.copy2(source, root / 'src' / source.name)
            result = subprocess.run([sys.executable, str(root / 'src/prepare_launch_home.py'), '--build'],
                                    cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Launch初期化テンプレートが見つかりません', result.stderr)
            self.assertFalse((root / 'config').exists())

if __name__ == '__main__':
    unittest.main()
