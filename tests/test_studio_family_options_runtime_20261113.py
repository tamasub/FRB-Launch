"""No Qt needed: validate the launch-to-Node composition bridge."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from launch_option_runtime import effective_options_path, find_node, find_studio_root


class OptionRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.launch = base / 'FRB_Launch'
        self.launch.joinpath('config').mkdir(parents=True)
        self.state = base / 'State'
        self.system = {
            'mode': 'embedded',
            'remember_login': True,
            'new_tab_url': 'https://www.google.com/',
            'default_zoom_percent': 80,
        }
        self.launch.joinpath('config/webview_settings.json').write_text(
            json.dumps(self.system), encoding='utf-8')

    def test_without_user_file_runtime_does_not_require_node_or_studio(self):
        self.assertEqual(effective_options_path(self.launch, self.state, 'webview'),
                         self.launch / 'config/webview_settings.json')
        self.assertFalse(self.state.exists())

    def test_user_file_requires_composition_and_never_clobbers_system(self):
        # During a standalone repo test, the Studio root may be elsewhere.
        # Use the bundled Studio Family source when both repos are available.
        sibling = Path(__file__).resolve().parents[2] / 'studio'
        if not (sibling / 'tools/option_settings/cli.mjs').is_file():
            self.skipTest('Studio Family repo not adjacent in this environment')
        if not find_node(self.launch, sibling):
            self.skipTest('Node is not installed')
        user = self.state / 'UserConfig'
        user.mkdir(parents=True)
        user.joinpath('webview_settings.json').write_text(
            '{"remember_login":false,"new_tab_url":"https://example.com/"}', encoding='utf-8')
        output = effective_options_path(self.launch, self.state, 'webview', configured_studio=sibling)
        data = json.loads(output.read_text(encoding='utf-8'))
        self.assertFalse(data['remember_login'])
        self.assertEqual(data['new_tab_url'], 'https://example.com/')
        self.assertEqual(data['default_zoom_percent'], 80)
        self.assertEqual(json.loads((self.launch / 'config/webview_settings.json').read_text()), self.system)
        self.assertEqual(json.loads((user / 'webview_settings.json').read_text())['remember_login'], False)

    def test_unknown_id_is_rejected(self):
        with self.assertRaises(ValueError):
            effective_options_path(self.launch, self.state, 'context_menu')


if __name__ == '__main__':
    unittest.main()
