#!/usr/bin/env python3
"""FRB Launch 0.9.5: validate compiled bundles, create GitHub pre-release feeds.

No update execution, no upload, no user-data writes (except configure-test phase).
Python standard library only. Do not change source/build artifacts in place.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import urllib.request
import urllib.error
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

INTEGRATED='0.9.5'
LAUNCH='0.9.3'
STUDIO='0.9.0'
UPDATER='0.9.5'
TAG='v0.9.5'


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def jsonfile(path: Path) -> dict:
    with path.open('r', encoding='utf-8-sig') as f:
        x=json.load(f)
    if not isinstance(x,dict):raise ValueError('Expected JSON object: '+str(path))
    return x


def atomic_json(path: Path, value:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def repo_valid(repo: str):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*',repo):
        raise ValueError('Repository must have owner/repository format: '+repr(repo))
    return repo


def asset_url(repo:str, name:str):
    return 'https://github.com/'+repo+'/releases/download/'+TAG+'/'+name


def inspect_secrets(launch_source:Path):
    """Check for plausible credential leaks, NOT personal paths or normal URLs."""
    confidential_keys=re.compile(r'(?i)^(?:password|passphrase|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|private[_-]?key|secret)$')
    suspicious_value=re.compile(r'(?:github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{25,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')
    candidates=[launch_source/'defaults/frb_launch_data.template.json']
    candidates+=list((launch_source/'config').rglob('*.json'))
    candidates+=list((launch_source/'defs').rglob('*.json'))
    for path in candidates:
        if not path.is_file():continue
        obj=jsonfile(path)
        stack=[(obj,'')]
        while stack:
            value,context=stack.pop()
            if isinstance(value,dict):
                for key,child in value.items():
                    loc=context+'/'+str(key)
                    if confidential_keys.match(str(key)) and isinstance(child,str) and child.strip() and not re.fullmatch(r'(?i)(?:example|placeholder|changeme|<.*>|\$\{.*\})',child.strip()):
                        raise ValueError(f'Possible credential property found: {path.name}:{loc} (value withheld)')
                    stack.append((child,loc))
            elif isinstance(value,list):
                stack.extend((child,context+'[]') for child in value)
            elif isinstance(value,str) and suspicious_value.search(value):
                raise ValueError(f'Possible credential pattern found: {path.name}:{context} (value withheld)')
    print('[OK] JSON credential pattern check passed; personal paths, menus and URLs are allowed.')


def bundle_paths(stage:Path) -> dict:
    return {
        'product':stage/f'FRBLaunch_{INTEGRATED}_update.zip',
        'portable':stage/f'FRBLaunch_{INTEGRATED}_portable.zip',
        'updater':stage/f'FRBUpdater_{UPDATER}.exe',
    }


def check_package(stage:Path, source:Path|None=None)->dict:
    paths=bundle_paths(stage)
    for path in paths.values():
        if not path.is_file() or path.stat().st_size<100:
            raise FileNotFoundError('Release artifact missing/empty: '+str(path))
    product,portable,updater=paths['product'],paths['portable'],paths['updater']
    with zipfile.ZipFile(product) as z:
        m=json.loads(z.read('release.json').decode('utf-8-sig'))
        expected={'launch':LAUNCH,'studio':STUDIO}
        if any((m.get('schema')!='frb-system-package-v1',m.get('product')!='FRBLaunchIntegrated',m.get('version')!=INTEGRATED,m.get('components')!=expected)):
            raise ValueError('Release manifest does not match 0.9.5 / Launch 0.9.3 / Studio 0.9.0')
        if not isinstance(m.get('files'),dict) or len(m['files'])<10:
            raise ValueError('Release manifest files missing')
        for target in ('FRBLaunch.exe','Studio/NativeShell/_publish/FRBStudio.NativeShell.exe'):
            if target not in m['files']:raise ValueError('Required system asset missing: '+target)
        if set(z.namelist()) != {'release.json'}|{'system/'+p for p in m['files']}:
            raise ValueError('Unexpected or missing files in updater ZIP')
        exe_hash=hashlib.sha256(z.read('system/FRBLaunch.exe')).hexdigest()
        if exe_hash!=m['files']['FRBLaunch.exe']:
            raise ValueError('Release Launch.exe SHA-256 mismatch')
    with zipfile.ZipFile(portable) as z:
        if not {'FRBLaunch/FRBLaunch.exe',f'FRBLaunch/updater/versions/{UPDATER}/FRBUpdater.exe','FRBLaunch/installed_release.json'}.issubset(set(z.namelist())):
            raise ValueError('Portable launch/updater/manifest incomplete')
        pm=json.loads(z.read('FRBLaunch/installed_release.json').decode('utf-8-sig'))
        if pm != m: raise ValueError('Portable inventory differs from updater ZIP')
        with z.open(f'FRBLaunch/updater/versions/{UPDATER}/FRBUpdater.exe') as fp:
            h=hashlib.sha256()
            for chunk in iter(lambda: fp.read(1024*1024),b''):
                h.update(chunk)
        if h.hexdigest()!=digest(updater):
            raise ValueError('Portable embedded Updater differs from published Updater')
    if source is not None:
        new_exe=source/'dist/FRBLaunch/FRBLaunch.exe'
        new_updater=source/'dist/updater/FRBUpdater.exe'
        if not new_exe.is_file() or exe_hash!=digest(new_exe):
            raise ValueError('Release ZIP Launch.exe does not match most recent local build')
        if not new_updater.is_file() or digest(new_updater)!=digest(updater):
            raise ValueError('Staged Updater differs from most recent local build')
    print(f'[OK] 0.9.5 bundle: {len(m["files"]):,} files, manifest and EXEs verified')
    return m


def create_feeds(stage:Path,repo:str,source:Path|None=None):
    repo_valid(repo)
    check_package(stage,source)
    paths=bundle_paths(stage)
    for name, obj in {
        'product_feed.json':{
            'schema':'frb-product-feed-v1','product':'FRBLaunchIntegrated','version':INTEGRATED,
            'components':{'launch':LAUNCH,'studio':STUDIO},
            'notes':'GitHub pre-release HTTPS update test; user-controlled update',
            'archive_url':asset_url(repo,paths['product'].name),
            'size':paths['product'].stat().st_size,'sha256':digest(paths['product'])
        },
        'updater_feed.json':{
            'schema':'frb-updater-feed-v1','version':UPDATER,
            'url':asset_url(repo,paths['updater'].name),
            'size':paths['updater'].stat().st_size,'sha256':digest(paths['updater'])
        }
    }.items():
        file=stage/name
        if file.exists():
            existing=jsonfile(file)
            if existing!=obj:
                raise FileExistsError('Feed already exists but content differs. Refusing to overwrite: '+str(file))
        else:
            atomic_json(file,obj)
    hashes=stage/f'SHA256_{INTEGRATED}.txt'
    # build_portable_distribution.py records portable, product, updater, whereas
    # bundle_paths() lists product, portable, updater. A checksum inventory is
    # a mapping of filename to hash: ordering (and Windows CRLF) is irrelevant.
    expected_checksums={path.name:digest(path) for path in paths.values()}
    if hashes.exists():
        actual_checksums={}
        for number, line in enumerate(hashes.read_text(encoding='utf-8-sig').splitlines(),1):
            if not line.strip():
                raise ValueError(f'Empty SHA256 inventory line {number}')
            match=re.fullmatch(r'([0-9a-fA-F]{64})  ([^/\\\r\n]+)',line)
            if not match:
                raise ValueError(f'Invalid SHA256 inventory line {number}')
            value, filename=match.groups()
            if filename in actual_checksums:
                raise ValueError(f'Duplicate SHA256 inventory entry: {filename}')
            actual_checksums[filename]=value.lower()
        for filename,expected_hash in expected_checksums.items():
            if filename not in actual_checksums:
                raise ValueError(f'Missing SHA256 inventory entry: {filename}')
            if actual_checksums[filename]!=expected_hash:
                raise ValueError(f'SHA256 mismatch for {filename}: staged artifact and inventory disagree')
        unexpected=set(actual_checksums)-set(expected_checksums)
        if unexpected:
            raise ValueError('Unexpected SHA256 inventory entries: '+', '.join(sorted(unexpected)))
    else:
        hashes.write_text(''.join(f'{value}  {name}\n' for name,value in expected_checksums.items()),encoding='utf-8')
    print('[OK] SHA256 inventory agrees with all 3 staged artifacts (order-independent)')
    notes=stage/'RELEASE_NOTES_0.9.5.md'
    if not notes.exists():
        notes.write_text('''# FRB Launch 0.9.5 — Preview\n\nWindows 11向け FRB Launch + FRB Studio 統合配布のGitHub更新テスト。\n\n- 統合版 0.9.5 / Launch 0.9.3 / Studio 0.9.0 / Updater 0.9.5\n- バージョン情報を自動確認し、控えめな更新通知を表示\n- ライトモードの視認性改善と、Updaterのフォント・進捗文言・配置調整\n- ZIP作成メニューの開発用パス参照を修正\n- 自動更新は行いません。更新開始はユーザー操作のみ\n\n**Pre-release（動作確認用）**。利用者独自のメニュー・パス・URLを含みます。\n''',encoding='utf-8')
    validate_feeds(stage,repo)
    print('[OK] GitHub pre-release assets and HTTPS feed files ready: '+str(stage))


def validate_feeds(stage:Path,repo:str):
    repo_valid(repo)
    paths=bundle_paths(stage)
    for name,key,schema,file in (
        ('product_feed.json','archive_url','frb-product-feed-v1',paths['product']),
        ('updater_feed.json','url','frb-updater-feed-v1',paths['updater'])
    ):
        info=jsonfile(stage/name)
        if info.get('schema')!=schema or info.get(key)!=asset_url(repo,file.name) or info.get('sha256')!=digest(file) or info.get('size')!=file.stat().st_size:
            raise ValueError('Invalid feed URL or hash/size: '+name)
    print('[OK] HTTPS feed URL, SHA-256, sizes and schema verified')


def online_check(stage:Path,repo:str):
    """Verify anonymous HTTPS retrieval. Do not download large archives here."""
    validate_feeds(stage,repo)
    for name in ('product_feed.json','updater_feed.json'):
        url=asset_url(repo,name)
        request=urllib.request.Request(url,headers={'User-Agent':'FRB-Update-Preflight/0.9.5'})
        with urllib.request.urlopen(request,timeout=25) as resp:
            final=resp.geturl()
            if not final.startswith('https://') or resp.status!=200:
                raise RuntimeError('HTTPS check failed: '+url)
            remote=json.loads(resp.read(128*1024+1).decode('utf-8-sig'))
        if remote != jsonfile(stage/name):
            raise ValueError('Published feed content differs from locally staged feed: '+name)
        print('[OK] Remote feed publicly accessible: '+url)
    for entry in (bundle_paths(stage)['product'],bundle_paths(stage)['updater']):
        url=asset_url(repo,entry.name)
        request=urllib.request.Request(url,method='HEAD',headers={'User-Agent':'FRB-Update-Preflight/0.9.5'})
        with urllib.request.urlopen(request,timeout=25) as resp:
            if resp.status!=200 or not resp.geturl().startswith('https://'):
                raise ValueError('GitHub release asset unavailable: '+url)
        print('[OK] Remote asset URL reachable: '+url)


def configure_test(install:Path,stage:Path,repo:str):
    online_check(stage,repo)
    install=install.resolve()
    if install.name.lower()!='frblaunch' or install.parent.name.lower()!='frb_update_test':
        raise ValueError('Safety guard: test target must end in FRB_Update_Test\\FRBLaunch')
    if not (install/'FRBLaunch.exe').is_file():
        raise FileNotFoundError('Test executable not found: '+str(install))
    current=jsonfile(install/'installed_release.json')
    if current.get('version')!='0.9.4' or current.get('components',{}).get('launch')!='0.9.2':
        raise ValueError('Expected test install is integrated 0.9.4 / Launch 0.9.2; found '+str(current.get('version')))
    journal_root=install.parent/('.'+install.name+'_update_backups')
    for file in journal_root.glob('*/journal.json'):
        if jsonfile(file).get('phase')=='applying':
            raise ValueError('Pending interrupted update Journal; recover first: '+str(file))
    config=install/'UserConfig/update_sources.json'
    if config.is_symlink() or config.parent.is_symlink():
        raise ValueError('Symlinked UserConfig not supported')
    desired={'schema':'frb-update-sources-v1',
             'updater_feed_url':asset_url(repo,'updater_feed.json'),
             'product_feed_url':asset_url(repo,'product_feed.json'),
             'allow_local_for_test':False}
    if config.is_file():
        old=jsonfile(config)
        if old==desired:
            print('[OK] Test UserConfig is already pointed at GitHub; no changes')
            return
        suffix=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid4().hex[:6]
        backup=config.with_name('update_sources.json.before_github_'+suffix+'.bak')
        backup.write_bytes(config.read_bytes())
        print('[BACKUP] '+str(backup))
    atomic_json(config,desired)
    print('[OK] TEST UserConfig switched to public GitHub feeds (no update started): '+str(config))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=('stage','verify','online','configure'),required=True)
    p.add_argument('--repo',required=True)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--source',type=Path)
    p.add_argument('--test-install',type=Path)
    a=p.parse_args()
    try:
        repo_valid(a.repo)
        if a.phase=='stage':
            if not a.source: raise ValueError('--source required for stage')
            inspect_secrets(a.source)
            create_feeds(a.stage,a.repo,a.source)
        elif a.phase=='verify':
            check_package(a.stage,a.source)
            validate_feeds(a.stage,a.repo)
        elif a.phase=='online':
            online_check(a.stage,a.repo)
        elif a.phase=='configure':
            if a.test_install is None:raise ValueError('--test-install required')
            configure_test(a.test_install,a.stage,a.repo)
        return 0
    except (OSError,ValueError,RuntimeError,urllib.error.URLError,zipfile.BadZipFile) as e:
        print('[ERROR] '+str(e),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
