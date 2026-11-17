"""Studio-owned app_version.json is the display source, independent of release.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from studio_version import read_studio_version


def write_version(studio, version, name='FRB Studio'):
    path = studio/'defs'/'app_version.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'app_name':name, 'app_version':version}), encoding='utf-8')


def test_explicit_studio_version_precedes_bundled_release(tmp_path):
    launch=tmp_path/'Launch'
    write_version(launch/'Studio', '0.9.0')
    authored=tmp_path/'AuthorStudio'
    write_version(authored, '0.9.1')
    assert read_studio_version(launch, launch, authored) == '0.9.1'
    assert read_studio_version(launch, launch) == '0.9.0'


def test_independent_sibling_and_bad_metadata(tmp_path):
    launch=tmp_path/'FRB_Launch'
    launch.mkdir()
    studio=tmp_path/'FRB_Studio'
    write_version(studio, '0.9.4')
    assert read_studio_version(launch) == '0.9.4'
    write_version(studio, 'oops')
    assert read_studio_version(launch) is None
    write_version(studio, '0.9.4', name='Not Studio')
    assert read_studio_version(launch) is None


def test_invalid_json_falls_back_to_installed_source(tmp_path):
    launch=tmp_path/'Launch'
    source=tmp_path/'AuthorStudio'
    write_version(source,'0.9.1')
    write_version(launch/'Studio','0.9.0')
    (source/'defs/app_version.json').write_text('{broken',encoding='utf-8')
    assert read_studio_version(launch, launch, source)=='0.9.0'


def test_dialog_uses_studio_version_before_manifest():
    source=(ROOT/'src/update_information_dialog.py').read_text('utf-8')
    caller=(ROOT/'src/app.py').read_text('utf-8')
    assert 'read_studio_version(self.launch_home, self.install_root, studio_root)' in source
    assert "studio_label = studio_version" in source
    assert '（配布記録）' in source
    assert "studio_root=self.expander().values.get('studio_root', '')" in caller


def test_studio_version_metadata_is_release_packaged():
    package=(ROOT/'scripts/build_release_package.py').read_text('utf-8')
    assert "or rel.startswith('data/json/00_rules/'))" in package
    assert "'defs/'" in package
    assert "'Studio'" in package
