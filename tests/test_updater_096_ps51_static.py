"""Static regression tests for the 0.9.6 PowerShell 5.1 staging script."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "prepare_FRBUpdater_0.9.6_GitHub_hotfix.ps1"
NOTES = ROOT / "docs" / "RELEASE_NOTES_Updater_0.9.6.md"


class TestPS51Compatibility(unittest.TestCase):
    def test_script_ascii_crlf_without_here_strings(self):
        payload = PS1.read_bytes()
        self.assertTrue(payload.isascii())
        self.assertNotIn(b"$notes = @'", payload)
        self.assertNotIn(b"@'", payload)
        self.assertNotIn(b"'@", payload)
        self.assertEqual(payload.count(b"\n"), payload.count(b"\r\n"))

    def test_release_notes_externalized(self):
        src = PS1.read_text(encoding="ascii")
        self.assertIn("docs\\RELEASE_NOTES_Updater_0.9.6.md", src)
        self.assertIn("ReadAllText($notesTemplate, [Text.Encoding]::UTF8)", src)
        self.assertIn("Write-Utf8New $notesFile", src)
        self.assertIn("起動許可", NOTES.read_text(encoding="utf-8"))

    def test_safety_guards_retained(self):
        src = PS1.read_text(encoding="ascii")
        for guard in ["Verify-Stage", "-PublishHotfix", "-ConfigureTestInstall", "0.9.4", "productFeedURL", "journal.json"]:
            self.assertIn(guard, src)


if __name__ == "__main__":
    unittest.main()
