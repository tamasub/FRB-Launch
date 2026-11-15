import importlib.util
import json
import tempfile
import unittest
import zipfile
import hashlib
from pathlib import Path
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/prepare_github_release_095.py'
spec=importlib.util.spec_from_file_location('ghprep',SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
REPO='tamasub/FRB-Launch'

class GithubTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.stage=self.root/'stage'
        self.stage.mkdir()
        self.source=self.root/'launch_source'
        (self.source/'dist/FRBLaunch').mkdir(parents=True)
        (self.source/'dist/updater').mkdir(parents=True)
        (self.source/'defaults').mkdir()
        (self.source/'config').mkdir()
        (self.source/'defs').mkdir()
        (self.source/'defaults/frb_launch_data.template.json').write_text(json.dumps({'pages':[{'title':'Local'}],'items':[{'path':r'F:\FRB_Apps\FRB_Launch','url':'https://example.com/x'}]}),encoding='utf-8')
        paths=m.bundle_paths(self.stage)
        launch=b'FRBLaunch EXE demo'*16
        updater=b'FRBUpdater EXE demo'*16
        (self.source/'dist/FRBLaunch/FRBLaunch.exe').write_bytes(launch)
        (self.source/'dist/updater/FRBUpdater.exe').write_bytes(updater)
        paths['updater'].write_bytes(updater)
        system={'FRBLaunch.exe':launch,'Studio/NativeShell/_publish/FRBStudio.NativeShell.exe':b'Studio EXE'}
        system.update({f'config/resource{i}.txt':f'File {i}'.encode() for i in range(15)})
        manifest={'schema':'frb-system-package-v1','product':'FRBLaunchIntegrated','version':'0.9.5','components':{'launch':'0.9.3','studio':'0.9.0'},'files':{k:hashlib.sha256(v).hexdigest() for k,v in system.items()}}
        with zipfile.ZipFile(paths['product'],'w') as z:
            z.writestr('release.json',json.dumps(manifest))
            for name,data in system.items():z.writestr('system/'+name,data)
        with zipfile.ZipFile(paths['portable'],'w') as z:
            z.writestr('FRBLaunch/installed_release.json',json.dumps(manifest))
            z.writestr('FRBLaunch/updater/versions/0.9.5/FRBUpdater.exe',updater)
            for name,data in system.items():z.writestr('FRBLaunch/'+name,data)
    def tearDown(self):self.tmp.cleanup()
    def test_stage_and_idempotent(self):
        m.inspect_secrets(self.source)
        m.create_feeds(self.stage,REPO,self.source)
        before={p.name:p.read_bytes() for p in self.stage.iterdir()}
        m.create_feeds(self.stage,REPO,self.source)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.stage.iterdir()})
        self.assertEqual(m.jsonfile(self.stage/'product_feed.json')['archive_url'],m.asset_url(REPO,'FRBLaunch_0.9.5_update.zip'))
        self.assertEqual(m.jsonfile(self.stage/'updater_feed.json')['version'],'0.9.5')
    def test_existing_checksum_inventory_in_builder_order(self):
        # The builder uses portable -> product -> updater, unlike bundle_paths().
        paths=m.bundle_paths(self.stage)
        sha=self.stage/'SHA256_0.9.5.txt'
        sha.write_bytes(('\r\n'.join(
            f'{m.digest(paths[key])}  {paths[key].name}'
            for key in ('portable','product','updater')
        )+'\r\n').encode('utf-8'))
        m.create_feeds(self.stage,REPO,self.source)
        before=sha.read_bytes()
        m.create_feeds(self.stage,REPO,self.source)
        self.assertEqual(sha.read_bytes(),before,'Existing inventory must not be overwritten')

    def test_real_checksum_mismatch_fails_without_overwriting(self):
        paths=m.bundle_paths(self.stage)
        sha=self.stage/'SHA256_0.9.5.txt'
        sha.write_text(''.join(
            f'{"0"*64 if key=="product" else m.digest(paths[key])}  {paths[key].name}\n'
            for key in ('portable','product','updater')
        ),encoding='utf-8')
        before=sha.read_bytes()
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch for FRBLaunch_0.9.5_update.zip'):
            m.create_feeds(self.stage,REPO,self.source)
        self.assertEqual(sha.read_bytes(),before)

    def test_duplicate_checksum_inventory_entry_fails(self):
        paths=m.bundle_paths(self.stage)
        sha=self.stage/'SHA256_0.9.5.txt'
        line=f'{m.digest(paths["portable"])}  {paths["portable"].name}\n'
        sha.write_text(line+line,encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Duplicate SHA256 inventory entry'):
            m.create_feeds(self.stage,REPO,self.source)

    def test_unknown_checksum_inventory_entry_fails(self):
        paths=m.bundle_paths(self.stage)
        sha=self.stage/'SHA256_0.9.5.txt'
        sha.write_text(''.join(f'{m.digest(p)}  {p.name}\n' for p in paths.values())+('0'*64)+'  unexpected.zip\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Unexpected SHA256 inventory entries'):
            m.create_feeds(self.stage,REPO,self.source)

    def test_no_wrong_repository_feed(self):
        m.create_feeds(self.stage,REPO,self.source)
        with self.assertRaises(ValueError):m.validate_feeds(self.stage,'example/wrong-repo')
    def test_zip_exe_mismatch_fails(self):
        m.bundle_paths(self.stage)['updater'].write_bytes(b'TAMPER'*30)
        with self.assertRaises(ValueError):m.check_package(self.stage,self.source)
    def test_secrets_blocked_but_paths_allowed(self):
        m.inspect_secrets(self.source)
        (self.source/'config/confidential.json').write_text(json.dumps({'api_key':'real_abcdef123'}))
        with self.assertRaisesRegex(ValueError,'Possible credential'):
            m.inspect_secrets(self.source)
    def test_test_config_backed_up(self):
        m.create_feeds(self.stage,REPO,self.source)
        install=self.root/'FRB_Update_Test/FRBLaunch'
        (install/'UserConfig').mkdir(parents=True)
        (install/'FRBLaunch.exe').write_bytes(b'old launch')
        (install/'installed_release.json').write_text(json.dumps({'version':'0.9.4','components':{'launch':'0.9.2','studio':'0.9.0'}}))
        cfg=install/'UserConfig/update_sources.json'
        cfg.write_text(json.dumps({'schema':'frb-update-sources-v1','updater_feed_url':'file:///tmp/u','product_feed_url':'file:///tmp/p','allow_local_for_test':True}))
        with patch.object(m,'online_check',return_value=None):m.configure_test(install,self.stage,REPO)
        self.assertFalse(m.jsonfile(cfg)['allow_local_for_test'])
        self.assertEqual(len(list(cfg.parent.glob('*.before_github_*.bak'))),1)
        with patch.object(m,'online_check',return_value=None):m.configure_test(install,self.stage,REPO)
        self.assertEqual(len(list(cfg.parent.glob('*.before_github_*.bak'))),1)
    def test_refuse_non_test_install(self):
        m.create_feeds(self.stage,REPO,self.source)
        with patch.object(m,'online_check',return_value=None):
            with self.assertRaises(ValueError):m.configure_test(self.root/'FRB_Apps/FRB_Launch',self.stage,REPO)

if __name__=='__main__':unittest.main()
