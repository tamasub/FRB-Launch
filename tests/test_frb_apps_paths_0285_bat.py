"""Regression tests for the Windows wrapper; tests do not execute cmd.exe."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / '_migrate_frb_apps_paths_0284.bat'

class TestWindowsBat(unittest.TestCase):
    def test_ascii_crlf(self):
        b = BAT.read_bytes()
        self.assertTrue(b.isascii())
        self.assertEqual(b.count(b'\n'), b.count(b'\r\n'))
        self.assertGreater(b.count(b'\r\n'), 30)

    def test_preview_then_choice_then_apply(self):
        t = BAT.read_text(encoding='ascii')
        preview = t.index('migrate_frb_apps_paths_0284.py" >')
        choice = t.index('choice /C YN /N')
        apply = t.index('migrate_frb_apps_paths_0284.py" --apply >')
        self.assertLess(preview, choice)
        self.assertLess(choice, apply)
        self.assertIn('if errorlevel 2 goto cancel', t)
        self.assertIn('if not "%RESULT%"=="0" goto fail_preview', t)

    def test_errors_pause_and_logs(self):
        t = BAT.read_text(encoding='ascii')
        self.assertIn('frb_launch_0284_preview_last.log', t)
        self.assertIn('frb_launch_0284_apply_last.log', t)
        self.assertIn(':finish_error', t)
        self.assertIn(':finish_ok', t)
        self.assertEqual(t.count('\npause\n'), 2)

if __name__ == '__main__':
    unittest.main()
