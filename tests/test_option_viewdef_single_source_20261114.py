"""Launch-authoritative ViewDef and compact, theme-aware option shell."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from launch_menu_registration import launch_view_def_path, studio_core_root

class LaunchViewDefContractTests(unittest.TestCase):
    def test_one_launch_owned_maintenance_viewdef(self):
        document=ROOT/'config/frb_launch_data.json'
        path=launch_view_def_path(document)
        self.assertEqual(path,ROOT/'defs/launch/frb_launch_maintenance_view_def_v0_1.json')
        definition=json.loads(path.read_text('utf-8'))
        views={v['id'] for v in definition['views']}
        self.assertIn('items_view',views)
        self.assertIn('app_alias_catalog_view',views)
        self.assertEqual(definition['app']['presentation']['density'],'compact')
        self.assertTrue(any(f['field']=='shuriken_button_index'
                            for s in definition['views'][0]['sections']
                            for f in s.get('fields',[])))

    def test_studio_launch_passes_canonical_path_not_studio_shadow(self):
        source=(ROOT/'src/app.py').read_text('utf-8')
        self.assertIn("'--launch-view-def='",source)
        self.assertIn("'frb_launch_maintenance_view_def_v0_1.json'",source)
        self.assertIn("theme=self.color_theme",source)
        bridge=(ROOT/'src/launch_menu_registration.py').read_text('utf-8')
        self.assertIn("launch_view_def_path(home / 'config'",bridge)
        self.assertIn("'view_def_path': str(launch_view_def_path(filename))",bridge)

    def test_compact_and_dark_theme_are_hosted_by_one_editor(self):
        source=(ROOT/'src/option_settings_window.py').read_text('utf-8')
        self.assertIn('self.resize(660, 530)',source)
        self.assertIn('&theme={self._theme}',source)
        self.assertIn('def set_theme(self, theme):',source)

if __name__=='__main__':unittest.main()
