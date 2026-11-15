"""Release pipeline unit checks with no GitHub access or Windows build."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

SRC = Path(__file__).parents[1] / 'scripts'
import sys
sys.path.insert(0, str(SRC))
import release_github_pipeline as release


def test_release_versions_must_be_explicit_and_numeric():
    for bad in ('x', '0.9', 'v0.9.6', '0.9.6-rc'):
        with pytest.raises(ValueError): release.require_version(bad)
    assert release.require_version('0.9.6') == '0.9.6'


def test_write_once_refuses_different_artifact(tmp_path):
    path=tmp_path/'test.txt'
    release.write_once(path,b'a')
    release.write_once(path,b'a')
    with pytest.raises(ValueError): release.write_once(path,b'b')
    assert path.read_bytes()==b'a'


def test_launch_version_must_match_embedded_source(tmp_path):
    source=tmp_path/'Launch'; (source/'src').mkdir(parents=True)
    (source/'src/app_version.py').write_text("APP_VERSION = '0.9.3'\n",'utf-8')
    studio=tmp_path/'Studio'; studio.mkdir()
    args=SimpleNamespace(version='0.9.6',launch_version='0.9.4',studio_version='0.9.0',
                         updater_version='0.9.6',launch_source=source,studio_source=studio)
    with pytest.raises(ValueError,match='BEFORE'):
        release.init_version(args)
    args.launch_version=''
    assert release.init_version(args)=='0.9.3'


def test_publish_requires_approval_before_any_gh(tmp_path, monkeypatch):
    args=SimpleNamespace(version='0.9.6',approved_tag='',stage=tmp_path)
    monkeypatch.setattr(release,'validate_plan',lambda x: {})
    def no_gh(*args):raise AssertionError('Must not call gh')
    monkeypatch.setattr(release,'gh',no_gh)
    with pytest.raises(ValueError,match='Human approval'):
        release.publish(args)


def test_recovery_uses_both_legacy_and_appdata(monkeypatch,tmp_path):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
    from frb_update.updater_core import backup_root,legacy_backup_root,backup_roots_for_recovery
    install=tmp_path/'test'/'FRBLaunch';install.mkdir(parents=True)
    assert backup_root(install) in backup_roots_for_recovery(install)
    assert legacy_backup_root(install) in backup_roots_for_recovery(install)


def test_preview_feed_url_stable_across_integrated_versions(tmp_path):
    args=SimpleNamespace(repo='tamasub/FRB-Launch',channel_branch='main',version='0.9.6')
    first=release.preview_feed_url(args,'product_feed.json')
    args.version='0.9.7'
    assert first==release.preview_feed_url(args,'product_feed.json')
    assert '/release-feed/preview/' in first


def test_preview_same_version_changed_hash_refused(tmp_path, monkeypatch):
    import base64
    args=SimpleNamespace(repo='tamasub/FRB-Launch',channel_branch='main',stage=tmp_path)
    new={'version':'0.9.6','sha256':'new'}
    (tmp_path/'product_feed.json').write_text(json.dumps(new)+'\n','utf-8')
    old={'version':'0.9.6','sha256':'old'}
    monkeypatch.setattr(release,'gh_contents',lambda *a: {
       'type':'file','content':base64.b64encode((json.dumps(old)+'\n').encode()).decode(),'sha':'fake'})
    with pytest.raises(ValueError,match='Same-version'):
        release.update_preview_file(args,'product_feed.json')


def test_preview_downgrade_refused(tmp_path, monkeypatch):
    import base64
    args=SimpleNamespace(repo='tamasub/FRB-Launch',channel_branch='main',stage=tmp_path)
    (tmp_path/'updater_feed.json').write_text(json.dumps({'version':'0.9.6'}),'utf-8')
    monkeypatch.setattr(release,'gh_contents',lambda *a: {
      'type':'file','content':base64.b64encode(json.dumps({'version':'0.9.7'}).encode()).decode(),'sha':'fake'})
    with pytest.raises(ValueError,match='roll back'):
        release.update_preview_file(args,'updater_feed.json')


def test_stage_feeds_freezes_urls_and_hashes(tmp_path, monkeypatch):
    args=SimpleNamespace(version='0.9.6',updater_version='0.9.6',studio_version='0.9.0',
        notes='F5 refresh',repo='tamasub/FRB-Launch',stage=tmp_path)
    release.legacy.INTEGRATED='0.9.6'
    release.legacy.LAUNCH='0.9.3'
    release.legacy.STUDIO='0.9.0'
    release.legacy.UPDATER='0.9.6'
    release.legacy.TAG='v0.9.6'
    product=tmp_path/'FRBLaunch_0.9.6_update.zip';product.write_bytes(b'fake product archive')
    portable=tmp_path/'FRBLaunch_0.9.6_portable.zip';portable.write_bytes(b'fake portable archive')
    updater=tmp_path/'FRBUpdater_0.9.6.exe';updater.write_bytes(b'fake updater')
    monkeypatch.setattr(release.legacy,'validate_feeds', lambda *a: None)
    plan=release.stage_feeds(args)
    assert plan['tag']=='v0.9.6'
    assert json.loads((tmp_path/'product_feed.json').read_text('utf-8'))['version']=='0.9.6'
    assert 'release_plan.json' in [p.name for p in tmp_path.iterdir()]
    # Repeating the same staging is allowed, changing even one byte is not.
    release.stage_feeds(args)
    product.write_bytes(b'changed')
    with pytest.raises(ValueError,match='inventory'):
        release.stage_feeds(args)


def test_ps_wrapper_is_ascii_crlf_with_interactive_confirmation():
    script=(Path(__file__).parents[1]/'release_FRBLaunch_GitHub.ps1').read_bytes()
    assert script.isascii()
    assert script.count(b'\r\n')==script.count(b'\n')
    assert b'Read-Host' in script and b'PUBLISH ' in script
    assert b'Invoke-ReleaseStep \'publish\'' in script
