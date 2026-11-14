"""Updater family: actual ZIP writes, corruption rollback, scope and bootstrap."""
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from frb_update.contracts import UpdateError,sha256_file,read_feed,version_tuple
from frb_update.bootstrap import ensure_updater,prepare_request,check_feeds
from frb_update.updater_core import install_zip,validate_zip,apply_request
from build_release_package import collect_files,build


def write_package(path,version,contents,extra_entries=None):
    manifest={'schema':'frb-system-package-v1','product':'FRBLaunchIntegrated',
              'version':version,'components':{'launch':'0.9.0','studio':'0.18.0'},
              'notes':'fixture','files':{p:hashlib.sha256(value).hexdigest() for p,value in contents.items()}}
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('release.json',json.dumps(manifest))
        for name,value in contents.items():z.writestr('system/'+name,value)
        for name,value in extra_entries or []:z.writestr(name,value)
    return manifest


def appfiles(launch=b'launch-v1',studio=b'studio-v1',**extra):
    result={'FRBLaunch.exe':launch,'Studio/NativeShell/_publish/FRBStudio.NativeShell.exe':studio}
    result.update(extra)
    return result

def test_success_and_user_isolation_and_stale_removal(tmp_path):
    install=tmp_path/'app';install.mkdir();(install/'FRBLaunch.exe').write_bytes(b'old')
    userdata=tmp_path/'FRBLaunch'/'UserData';userdata.mkdir(parents=True)
    live=userdata/'frb_launch_data.json';live.write_text('{"personal":"keep"}','utf-8')
    legacy=install/'config'/'frb_launch_data.json';legacy.parent.mkdir();legacy.write_text('old config','utf-8')
    one=tmp_path/'v1.zip'
    write_package(one,'1.0.0',appfiles(**{'legacy_system.txt':b'outdated'}))
    backup=install_zip(one,install)
    assert backup.exists()
    assert (install/'legacy_system.txt').read_bytes()==b'outdated'
    two=tmp_path/'v2.zip';write_package(two,'1.0.1',appfiles(launch=b'new'))
    install_zip(two,install)
    assert (install/'FRBLaunch.exe').read_bytes()==b'new'
    assert not (install/'legacy_system.txt').exists()
    assert live.read_text('utf-8')=='{"personal":"keep"}'
    assert legacy.read_text('utf-8')=='old config'
    assert json.loads((install/'installed_release.json').read_text())['version']=='1.0.1'

def test_error_rolls_back_and_restores_manifest(tmp_path):
    root=tmp_path/'app';root.mkdir();(root/'FRBLaunch.exe').write_bytes(b'old')
    one=tmp_path/'one.zip';write_package(one,'1.0.0',appfiles(launch=b'first'))
    install_zip(one,root)
    state_before=(root/'installed_release.json').read_bytes()
    two=tmp_path/'two.zip';write_package(two,'1.0.1',appfiles(launch=b'next'))
    with pytest.raises(OSError,match='simulated'):
        install_zip(two,root,fault_after=1)
    assert (root/'FRBLaunch.exe').read_bytes()==b'first'
    assert (root/'installed_release.json').read_bytes()==state_before

def test_reject_unauthorized_or_modified_archives(tmp_path):
    for rel in ('../UserData/secret','config/frb_launch_data.json','updater/FRBUpdater.exe','UserConfig/webview.json','Studio/data/json/01_main/private.json'):
        package=tmp_path/(rel.replace('/','_')+'.zip')
        write_package(package,'1.0.0',appfiles(**{rel:b'changed'}))
        with pytest.raises(UpdateError):validate_zip(package)
    extra=tmp_path/'extra.zip';write_package(extra,'1.0.0',appfiles(),extra_entries=[('system/userfile.txt',b'bad')])
    with pytest.raises(UpdateError):validate_zip(extra)
    tamper=tmp_path/'tamper.zip'
    data=appfiles();data['FRBLaunch.exe']=b'legit'
    manifest=write_package(tamper,'1.0.0',data)
    with zipfile.ZipFile(tamper,'w') as z:
        z.writestr('release.json',json.dumps(manifest))
        for name,v in data.items():z.writestr('system/'+name,v if name!='FRBLaunch.exe' else b'bad')
    with pytest.raises(UpdateError):validate_zip(tamper)

def test_updater_bootstrap_local_feed_and_product_request(tmp_path):
    updater_bytes=b'mock-executable-for-hash'
    executable=tmp_path/'FRBUpdater.exe';executable.write_bytes(updater_bytes)
    package=tmp_path/'release.zip';write_package(package,'1.0.1',appfiles())
    updater={'schema':'frb-updater-feed-v1','version':'0.1.0',
             'url':executable.as_uri(),'size':executable.stat().st_size,'sha256':sha256_file(executable)}
    product={'schema':'frb-product-feed-v1','product':'FRBLaunchIntegrated','version':'1.0.1',
             'archive_url':package.as_uri(),'size':package.stat().st_size,'sha256':sha256_file(package),
             'components':{'launch':'0.9.0','studio':'0.18.0'},
             'notes':'test'}
    updater_file=tmp_path/'u.json';updater_file.write_text(json.dumps(updater),'utf-8')
    product_file=tmp_path/'p.json';product_file.write_text(json.dumps(product),'utf-8')
    with pytest.raises(UpdateError):check_feeds(updater_file.as_uri(),product_file.as_uri())
    feeds=check_feeds(updater_file.as_uri(),product_file.as_uri(),allow_local=True)
    root=tmp_path/'app';root.mkdir();(root/'FRBLaunch.exe').write_bytes(b'old')
    binary=ensure_updater(root,feeds[0],allow_local=True)
    assert binary.read_bytes()==updater_bytes
    assert ensure_updater(root,feeds[0],allow_local=True)==binary
    request=prepare_request(feeds[1],tmp_path/'work',allow_local=True)
    apply_request(request,root,allow_local=True)
    assert (root/'installed_release.json').exists()
    assert not (tmp_path/'work'/'pending_update.json').is_dir()

def test_builder_omits_personal_files_and_preserves_defaults(tmp_path):
    launch=tmp_path/'dist';launch.mkdir();(launch/'FRBLaunch.exe').write_bytes(b'launch')
    (launch/'launch_home.json').write_text('{"launch_home":"../.."}')
    studio=tmp_path/'studio';(studio/'NativeShell'/'_publish').mkdir(parents=True)
    (studio/'NativeShell'/'_publish'/'FRBStudio.NativeShell.exe').write_bytes(b'studio')
    (studio/'tools'/'option_settings').mkdir(parents=True)
    (studio/'tools'/'option_settings'/'cli.mjs').write_text('')
    (studio/'runtime'/'node').mkdir(parents=True)
    (studio/'runtime'/'node'/'node.exe').write_bytes(b'node')
    source=tmp_path/'src';(source/'defaults').mkdir(parents=True)
    (source/'defaults'/'frb_launch_data.template.json').write_text('{"template":true}')
    (source/'config').mkdir();(source/'config'/'frb_launch_data.json').write_text('personal')
    (source/'config'/'file_index_options.json').write_text('{"system":true}')
    (studio/'data'/'json'/'01_main').mkdir(parents=True)
    (studio/'data'/'json'/'01_main'/'private.json').write_text('\"my secret\"')
    output=tmp_path/'ready.zip'
    build(SimpleNamespace(version='1.0.0',launch_version='0.9.0',studio_version='0.18.0',
                          launch_dist=launch,studio_runtime=studio,launch_source=source,
                          output=output,notes='test',archive_url=''))
    with zipfile.ZipFile(output) as z:
        assert 'system/defaults/frb_launch_data.template.json' in z.namelist()
        assert 'system/config/file_index_options.json' in z.namelist()
        assert 'system/config/frb_launch_data.json' not in z.namelist()
        assert 'system/launch_home.json' not in z.namelist()
        assert 'system/Studio/data/json/01_main/private.json' not in z.namelist()

def test_version_comparison():
    assert version_tuple('1.0.10')>version_tuple('1.0.9')
    with pytest.raises(UpdateError):version_tuple('1.0')


def test_machine_specific_git_config_moves_once(tmp_path):
    from launch_user_settings import ensure_user_settings
    src=tmp_path/'system.json';src.write_text('{"path":"F:/FRB"}','utf-8')
    user=tmp_path/'UserConfig'/'git_commit_options.json'
    assert ensure_user_settings(src,user)==user
    user.write_text('{"path":"D:/private"}','utf-8')
    src.write_text('{"path":"C:/other"}','utf-8')
    ensure_user_settings(src,user)
    assert json.loads(user.read_text())['path']=='D:/private'
