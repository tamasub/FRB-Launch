"""No-GUI regression tests for the Python build/migration contract."""
from pathlib import Path
import tempfile
import sys
import unittest
import zipfile

from python_build_environment import supports_build
from make_launch_zip import make_zip
from refresh_python_environment import python_identity, rollback

ROOT = Path(__file__).resolve().parents[1]


class PythonBuildEnvironmentTests(unittest.TestCase):
    def test_supported_versions(self):
        for v in [(3, 10, 0), (3, 14, 8), (3, 15, 2), (3, 15, 3)]:
            self.assertTrue(supports_build(v, 64, False, "AMD64"))
        for v in [(3, 9, 9), (3, 15, 0), (3, 15, 1), (3, 16, 0)]:
            self.assertFalse(supports_build(v, 64, False, "AMD64"))
        self.assertFalse(supports_build((3, 15, 2), 32, False, "AMD64"))
        self.assertFalse(supports_build((3, 15, 2), 64, True, "AMD64"))
        self.assertFalse(supports_build((3, 15, 2), 64, False, "ARM64"))
        self.assertFalse(supports_build((3, 14, 8), 64, False, "AMD64", migration=True))
        self.assertTrue(supports_build((3, 15, 2), 64, False, "AMD64", migration=True))

    def test_default_new_venv_and_refresh_use_315(self):
        build = (ROOT / "_build_windows.bat").read_text()
        refresh = (ROOT / "update_python_env.bat").read_text()
        self.assertIn("py -3.15 -m venv .venv", build)
        self.assertIn("py -3.15", refresh)
        self.assertNotIn("py -3.14", refresh)
        self.assertLess(build.index("--dependencies"), build.index("taskkill"))
        self.assertLess(build.index("smoke_context_menu_native_gui.py"), build.index("build_output_preflight.py"))

    def test_requirements_preserve_legacy_and_add_webengine(self):
        from packaging.requirements import Requirement
        reqs = [Requirement(x) for x in (ROOT / "requirements.txt").read_text().splitlines()
                if x and not x.startswith("#")]
        for py, expected in [("3.14", {"PySide6": "==6.10.1", "pyinstaller": "==6.17.0", "tzdata": "==2025.2"}),
                             ("3.15", {"PySide6": "==6.12.0", "PySide6-WebEngine": "==6.12.0.140", "pyinstaller": "==6.22.3", "tzdata": "==2025.2"})]:
            actual = {r.name: str(r.specifier) for r in reqs if r.marker is None or r.marker.evaluate({"python_version": py})}
            self.assertEqual(actual, expected)

    def test_interpreter_probe_returns_version_and_threading(self):
        identity = python_identity(Path(sys.executable))
        self.assertEqual(identity["version"], list(sys.version_info[:3]))
        self.assertIsInstance(identity["free_threaded"], bool)

    def test_rollback_restores_old_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            venv = root / ".venv"
            backup = root / ".venv_backup_test"
            venv.mkdir()
            backup.mkdir()
            (venv / "new.txt").write_text("new")
            (backup / "old.txt").write_text("old")
            rollback(venv, backup)
            self.assertEqual((venv / "old.txt").read_text(), "old")
            self.assertFalse((venv / "new.txt").exists())
            self.assertFalse(backup.exists())

    def test_venv_backup_excluded_from_source_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (".venv", ".venv_backup_20261125_190000", ".venv_failed_20261125_190001", "src"):
                (root / name).mkdir()
                (root / name / "sample.txt").write_text("sample")
            with zipfile.ZipFile(make_zip(root)) as archive:
                self.assertEqual(archive.namelist(), ["src/sample.txt"])


if __name__ == "__main__":
    unittest.main()
