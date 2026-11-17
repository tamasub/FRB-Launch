import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_FRBLaunch_094_test_feeds import (
    check_test_install, check_feeds, configure_test_sources,
    stage_feeds, validate_release, run, read_json)


def setup_demo(tmp_path):
    install = tmp_path/'FRB_Update_Test'/'FRBLaunch'
    install.mkdir(parents=True)
    (install/'FRBLaunch.exe').write_bytes(b'installed')
    (install/'installed_release.json').write_text(json.dumps({
        'version':'0.9.3', 'components':{'launch':'0.9.1','studio':'0.9.0'}}))
    release=tmp_path/'release'
    release.mkdir()
    binary=b'new-updater'
    (release/'FRBUpdater_0.9.4.exe').write_bytes(binary)
    fake_launch=b'new-launch'
    manifest={'schema':'frb-system-package-v1','product':'FRBLaunchIntegrated',
              'version':'0.9.4','components':{'launch':'0.9.2','studio':'0.9.0'},
              'files':{'FRBLaunch.exe':hashlib.sha256(fake_launch).hexdigest()}}
    with zipfile.ZipFile(release/'FRBLaunch_0.9.4_PRIVATE_REVIEW_update.zip','w') as z:
        z.writestr('release.json',json.dumps(manifest))
        z.writestr('system/FRBLaunch.exe',fake_launch)
    with zipfile.ZipFile(release/'FRBLaunch_0.9.4_PRIVATE_REVIEW_portable.zip','w') as z:
        z.writestr('FRBLaunch/FRBLaunch.exe',fake_launch)
        z.writestr('FRBLaunch/updater/versions/0.9.4/FRBUpdater.exe',binary)
    return install,release


def test_stage_feeds_preserves_config_and_is_idempotent(tmp_path):
    install,rel=setup_demo(tmp_path)
    system=install/'defs/update/update_sources.json'
    system.parent.mkdir(parents=True)
    system.write_text(json.dumps({'schema':'frb-update-sources-v1',
        'updater_feed_url':'','product_feed_url':'',
        'allow_local_for_test':False,'custom':'important'}))
    product, portable, updater, manifest=validate_release(rel)
    stage_feeds(rel,product,updater,manifest)
    check_feeds(rel,product,updater)
    configure_test_sources(install,rel)
    assert read_json(system)['custom']=='important'
    assert read_json(install/'UserConfig/update_sources.json')['allow_local_for_test'] is True
    assert read_json(install/'UserConfig/update_sources.json')['product_feed_url'].startswith('file:')
    before=sorted(system.parent.glob('*.bak'))
    configure_test_sources(install,rel)
    assert sorted(system.parent.glob('*.bak'))==before
    check_test_install(install,{'0.9.3'})


def test_refuses_non_test_install(tmp_path):
    root=tmp_path/'FRB_Apps'/'FRBLaunch';root.mkdir(parents=True)
    (root/'FRBLaunch.exe').write_bytes(b'exe')
    (root/'installed_release.json').write_text(json.dumps({'version':'0.9.3'}))
    with pytest.raises(ValueError,match='Safety guard'):
        check_test_install(root,{'0.9.3'})


def test_does_not_replace_non_test_user_config(tmp_path):
    install,rel=setup_demo(tmp_path)
    user=install/'UserConfig/update_sources.json'
    user.parent.mkdir(parents=True)
    user.write_text(json.dumps({'schema':'frb-update-sources-v1',
         'updater_feed_url':'https://example.net/updater',
         'product_feed_url':'https://example.net/product','allow_local_for_test':False}))
    with pytest.raises(ValueError,match='Non-target Feed'):
        configure_test_sources(install,rel)
    assert 'example.net' in user.read_text()
    assert not (install/'defs/update/update_sources.json').exists()


def test_rejects_interrupted_update(tmp_path):
    install,rel=setup_demo(tmp_path)
    journal=install.parent/'.FRBLaunch_update_backups'/'a'/'journal.json'
    journal.parent.mkdir(parents=True)
    journal.write_text(json.dumps({'phase':'applying'}))
    with pytest.raises(ValueError,match='Unrecovered'):
        check_test_install(install,{'0.9.3'})


def test_rejects_wrong_manifest(tmp_path):
    install,rel=setup_demo(tmp_path)
    update=rel/'FRBLaunch_0.9.4_PRIVATE_REVIEW_update.zip'
    with zipfile.ZipFile(update,'w') as z:
        z.writestr('release.json',json.dumps({'version':'0.9.3'}))
    with pytest.raises(ValueError,match='version/schema'):
        validate_release(rel)


def test_refresh_does_not_rewrite_release_files(tmp_path):
    install,rel=setup_demo(tmp_path)
    product,portable,updater,manifest=validate_release(rel)
    stage_feeds(rel,product,updater,manifest)
    files=[product,portable,updater]
    contents=[f.read_bytes() for f in files]
    run('refresh',tmp_path/'unused',tmp_path/'unused',rel,install)
    assert [f.read_bytes() for f in files]==contents
    state=read_json(install/'installed_release.json');state['version']='0.9.4'
    state['components']['launch']='0.9.2'
    (install/'installed_release.json').write_text(json.dumps(state))
    run('refresh',tmp_path/'unused',tmp_path/'unused',rel,install)
