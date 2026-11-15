"""Release 0.9.8: first-install feed sources must ship in BOTH distributions.
Tests are offline, use throwaway temp paths and never touch an installed Launch.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import zipfile

import pytest

sys.path.insert(0,str(Path(__file__).parents[1] / 'scripts'))
import release_github_pipeline as release

DEFAULT = Path(__file__).parents[1] / 'defs/update/update_sources.json'


def args(tmp_path):
    return SimpleNamespace(
        launch_source=tmp_path / 'source',
        repo='tamasub/FRB-Launch', channel_branch='main',
        stage=tmp_path / 'stage', version='0.9.8')


def test_default_template_has_both_stable_urls():
    cfg = json.loads(DEFAULT.read_text('utf-8'))
    a = SimpleNamespace(repo='tamasub/FRB-Launch',channel_branch='main',version='0.9.8')
    assert cfg == release.required_initial_sources(a)
    assert cfg['updater_feed_url'].startswith('https://')
    assert cfg['product_feed_url'].startswith('https://')
    assert 'v0.9.8' not in json.dumps(cfg)


def test_reject_missing_or_wrong_urls(tmp_path):
    a = args(tmp_path)
    good = release.required_initial_sources(a)
    release.validate_initial_sources(a, good, 'test')
    for change in (
        {'updater_feed_url': ''},
        {'product_feed_url': ''},
        {'product_feed_url': 'https://github.com/tamasub/FRB-Launch/releases/download/v0.9.8/product_feed.json'},
        {'allow_local_for_test': True},
        {'updater_feed_url': 'file:///C:/feed.json'},
    ):
        cfg={**good, **change}
        with pytest.raises(ValueError,match='Fresh-install'):
            release.validate_initial_sources(a,cfg,'bad')


def test_source_preflight_works_and_does_not_write(tmp_path):
    a=args(tmp_path)
    config=a.launch_source / 'defs/update/update_sources.json'
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(release.required_initial_sources(a)),'utf-8')
    before=config.read_bytes()
    release.check_initial_sources_file(a)
    assert config.read_bytes()==before
    config.write_text('{}','utf-8')
    with pytest.raises(ValueError, match='Fresh-install'):
        release.check_initial_sources_file(a)


def test_both_distributions_must_embed_valid_sources(tmp_path,monkeypatch):
    a=args(tmp_path)
    a.stage.mkdir()
    contents=release.required_initial_sources(a)
    portable=a.stage/'portable.zip'
    update=a.stage/'update.zip'
    entries={'portable':'FRBLaunch/defs/update/update_sources.json',
             'product':'system/defs/update/update_sources.json'}
    def write_archive(file, entry, cfg):
        with zipfile.ZipFile(file,'w') as archive:
            archive.writestr(entry,json.dumps(cfg))
    write_archive(portable,entries['portable'],contents)
    write_archive(update,entries['product'],contents)
    monkeypatch.setattr(release,'paths', lambda _: {'portable':portable,'product':update})
    release.check_initial_sources_archives(a)
    write_archive(portable,entries['portable'],{**contents,'updater_feed_url':''})
    with pytest.raises(ValueError,match='Fresh-install'):
        release.check_initial_sources_archives(a)
    write_archive(portable,entries['portable'],contents)
    write_archive(update,'system/some_other_file.json',contents)
    with pytest.raises(ValueError,match='Cannot validate update URLs'):
        release.check_initial_sources_archives(a)


def test_clean_install_migrates_default_to_user_config_but_preserves_existing(tmp_path):
    sys.path.insert(0,str(Path(__file__).parents[1] / 'src'))
    from frb_update.contracts import read_sources
    a=args(tmp_path)
    source=a.launch_source/'defs/update/update_sources.json'
    source.parent.mkdir(parents=True)
    good=release.required_initial_sources(a)
    source.write_text(json.dumps(good),encoding='utf-8')
    user=tmp_path/'fresh_install/UserConfig/update_sources.json'
    assert read_sources(source,user_path=user)==good
    assert json.loads(user.read_text('utf-8'))==good
    # Existing installations and reproduction devices must not be auto-rewritten.
    existing={**good, 'updater_feed_url':'', 'product_feed_url':''}
    user.write_text(json.dumps(existing),encoding='utf-8')
    assert read_sources(source,user_path=user)==existing
    assert json.loads(user.read_text('utf-8'))==existing
