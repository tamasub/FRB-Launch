#!/usr/bin/env python3
"""Versioned, resumable GitHub release pipeline for FRB Launch (stdlib only).

Stage is local. Publish requires explicit human confirmation at the PS entry point;
this executable also requires --approved-tag matching the immutable release tag.
Never silently overwrite published GitHub assets or local release artifacts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import prepare_github_release_095 as legacy

VERSION_RE = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+$')


def fail(message):
    raise ValueError(message)


def require_version(value):
    if not VERSION_RE.fullmatch(value):
        fail('Version must be numeric MAJOR.MINOR.PATCH: ' + value)
    return value


def sha256(path):
    return legacy.digest(Path(path))


def init_version(args):
    for item in (args.version, args.studio_version, args.updater_version):
        require_version(item)
    legacy.INTEGRATED = args.version
    legacy.STUDIO = args.studio_version
    legacy.UPDATER = args.updater_version
    legacy.TAG = 'v' + args.version
    source_version = (args.launch_source/'src/app_version.py').read_text('utf-8-sig')
    match = re.search(r'(?m)^APP_VERSION\s*=\s*[\'\"]([0-9]+\.[0-9]+\.[0-9]+)[\'\"]\s*$', source_version)
    if not match:
        fail('APP_VERSION declaration not recognized in src/app_version.py')
    legacy.LAUNCH = match.group(1)
    if args.launch_version and args.launch_version != legacy.LAUNCH:
        fail('Requested Launch version '+args.launch_version+' != APP_VERSION '+legacy.LAUNCH+
             '. Change source version BEFORE the manual _build_windows.bat, then rebuild.')
    if not args.launch_source.is_dir() or not args.studio_source.is_dir():
        fail('Source folders missing')
    return legacy.LAUNCH


def paths(args):
    return legacy.bundle_paths(args.stage)


def require_fresh_builds(args):
    source = args.launch_source
    launch_exe = source/'dist/FRBLaunch/FRBLaunch.exe'
    studio_exe = args.studio_source/'NativeShell/_publish/FRBStudio.NativeShell.exe'
    updater_exe = source/'dist/updater/FRBUpdater.exe'
    for file in (launch_exe, studio_exe, updater_exe):
        if not file.is_file():
            fail('Built EXE missing: '+str(file))
    # A newer source means the compiled executable cannot contain that change.
    launch_sources = ('app.py','expanded_view.py','remote_files_explorer.py',
                      'app_version.py','update_information_dialog.py')
    updater_sources = ('frb_updater_main.py','frb_update/updater_core.py',
                       'frb_update/progress_ui.py','frb_update/progress_gate.py',
                       'frb_update/contracts.py')
    for exe, names, cmd in ((launch_exe,launch_sources,'_build_windows.bat'),
                             (updater_exe,updater_sources,'_build_updater_windows.bat')):
        for name in names:
            file = source/'src'/name
            if file.is_file() and file.stat().st_mtime_ns > exe.stat().st_mtime_ns:
                fail('Stale EXE: '+str(file)+' newer than '+str(exe)+'; run '+cmd)
    return launch_exe, updater_exe


def write_once(path, content: bytes):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != content:
            fail('Immutable staged file differs: '+str(path))
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        tmp.write_bytes(content)
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def json_bytes(obj):
    return (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def feed_objects(args):
    asset=paths(args)
    repo=args.repo
    return {
      'product_feed.json': {
        'schema':'frb-product-feed-v1','product':'FRBLaunchIntegrated','version':args.version,
        'components':{'launch':legacy.LAUNCH,'studio':args.studio_version},
        'notes':args.notes,
        'archive_url':legacy.asset_url(repo,asset['product'].name),
        'size':asset['product'].stat().st_size,'sha256':sha256(asset['product'])
      },
      'updater_feed.json': {
        'schema':'frb-updater-feed-v1','version':args.updater_version,
        'url':legacy.asset_url(repo,asset['updater'].name),
        'size':asset['updater'].stat().st_size,'sha256':sha256(asset['updater'])
      }
    }


def asset_files(args):
    p=paths(args)
    return [p['portable'], p['product'], p['updater'], args.stage/f'SHA256_{args.version}.txt',
            args.stage/'product_feed.json', args.stage/'updater_feed.json']


def stage_feeds(args):
    files=paths(args)
    inventory={file.name:sha256(file) for file in files.values()}
    hashfile=args.stage/f'SHA256_{args.version}.txt'
    if hashfile.exists():
        actual={}
        for line in hashfile.read_text('utf-8-sig').splitlines():
            m=re.fullmatch(r'([a-fA-F0-9]{64})  ([^\\/\r\n]+)',line)
            if not m or m.group(2) in actual:
                fail('Invalid or duplicate SHA256 inventory line')
            actual[m.group(2)]=m.group(1).lower()
        if actual!=inventory:
            fail('Existing SHA256 inventory disagrees with release artifacts')
    else:
        write_once(hashfile,(''.join(f'{value}  {name}\n' for name,value in inventory.items())).encode('utf-8'))
    for name,obj in feed_objects(args).items():
        write_once(args.stage/name,json_bytes(obj))
    text=(f'# FRB Launch {args.version} — Preview\n\n'
          f'- Integrated: {args.version}\n- Launch: {legacy.LAUNCH}\n'
          f'- Studio: {args.studio_version}\n- Updater: {args.updater_version}\n'
          f'- Changes: {args.notes}\n\n'
          'GitHub pre-release. Updates require an explicit user action.\n'
          'The approved initial menu may contain user-specific paths and URLs.\n')
    write_once(args.stage/f'RELEASE_NOTES_{args.version}.md',text.encode('utf-8'))
    legacy.validate_feeds(args.stage,args.repo)
    plan={
        'schema':'frb-github-release-plan-v1',
        'repo':args.repo,'tag':'v'+args.version,'integrated_version':args.version,
        'launch_version':legacy.LAUNCH,'studio_version':args.studio_version,
        'updater_version':args.updater_version,
        'assets':{file.name:{'size':file.stat().st_size,'sha256':sha256(file)}
                  for file in asset_files(args)}
    }
    write_once(args.stage/'release_plan.json',json_bytes(plan))
    print('[OK] Immutable feeds, hashes and release plan verified')
    return plan


def validate_plan(args):
    check_initial_sources_file(args)
    p=paths(args)
    for f in p.values():
        if not f.is_file():
            fail('Missing artifact: '+str(f))
    check_initial_sources_archives(args)
    manifest=legacy.check_package(args.stage,args.launch_source)
    if manifest.get('version')!=args.version:
        fail('Integrated version mismatch')
    legacy.validate_feeds(args.stage,args.repo)
    plan_path=args.stage/'release_plan.json'
    if not plan_path.is_file():
        fail('Release plan missing; run stage first')
    plan=legacy.jsonfile(plan_path)
    if (plan.get('repo')!=args.repo or plan.get('tag')!='v'+args.version or
        plan.get('launch_version')!=legacy.LAUNCH or
        plan.get('studio_version')!=args.studio_version or
        plan.get('updater_version')!=args.updater_version):
        fail('Release plan differs from source/version')
    expected={file.name:{'size':file.stat().st_size,'sha256':sha256(file)}
              for file in asset_files(args)}
    if plan.get('assets')!=expected:
        fail('Staged asset changed after approval')
    hashes={}
    for line in (args.stage/f'SHA256_{args.version}.txt').read_text('utf-8').splitlines():
        m=re.fullmatch(r'([0-9a-fA-F]{64})  ([^\\/\r\n]+)',line)
        if not m or m.group(2) in hashes:fail('Invalid SHA256 inventory')
        hashes[m.group(2)]=m.group(1).lower()
    if hashes!={p.name:sha256(p) for p in paths(args).values()}:
        fail('SHA256 inventory mismatch')
    print('[OK] Immutable artifacts / versions / feed / SHA / plan verified')
    return plan


def stage(args):
    check_initial_sources_file(args)
    if args.stage.exists() and not args.stage.is_dir():fail('Stage must be a directory')
    args.stage.mkdir(parents=True,exist_ok=True)
    legacy.inspect_secrets(args.launch_source)
    p=paths(args)
    exists=[p['portable'].exists(),p['product'].exists()]
    if any(exists) and not all(exists):
        fail('Partial archive output. Inspect stage; no overwrite or delete')
    if not any(exists):
        require_fresh_builds(args)
        cmd=[str(args.python),str(args.launch_source/'scripts/build_portable_distribution.py'),
             '--launch-source',str(args.launch_source), '--studio-source',str(args.studio_source),
             '--output',str(args.stage), '--version',args.version,
             '--launch-version',legacy.LAUNCH, '--studio-version',args.studio_version,
             '--updater-version',args.updater_version, '--notes',args.notes,'--approve-template']
        subprocess.run(cmd,cwd=args.launch_source,check=True)
    else:
        print('[INFO] Existing immutable ZIPs reused (no overwrite)')
    # `check_package` compares the built source exe to the contents of the ZIP.
    legacy.check_package(args.stage,args.launch_source)
    stage_feeds(args)
    validate_plan(args)
    print('[SAFE] Staged. Nothing uploaded or installed: '+str(args.stage))


def gh(args,*cmd):
    exe=shutil.which('gh')
    if not exe:fail('GitHub CLI missing (gh). Install and run gh auth login')
    proc=subprocess.run([exe,*map(str,cmd)],encoding='utf-8',errors='replace',
                        capture_output=True)
    return proc


def gh_json(args,*cmd):
    run=gh(args,*cmd)
    if run.returncode:fail('GitHub CLI failed: '+run.stderr.strip()[:500])
    try: return json.loads(run.stdout)
    except ValueError as exc:raise ValueError('Invalid JSON from GitHub CLI') from exc



def preview_feed_url(args, name):
    if name not in ('updater_feed.json', 'product_feed.json'):
        fail('Invalid preview feed filename')
    return ('https://raw.githubusercontent.com/' + args.repo + '/' +
            args.channel_branch + '/release-feed/preview/' + name)


# A clean installation must discover new releases without manual configuration.
# Check source AND immutable archive contents; never modify installed UserConfig.
def required_initial_sources(args):
    return {
        'schema': 'frb-update-sources-v1',
        'updater_feed_url': preview_feed_url(args, 'updater_feed.json'),
        'product_feed_url': preview_feed_url(args, 'product_feed.json'),
        'allow_local_for_test': False,
    }


def validate_initial_sources(args, payload, where):
    if not isinstance(payload, dict) or payload != required_initial_sources(args):
        fail('Fresh-install update URLs are missing or incorrect in ' + str(where)
             + '; configure defs/update/update_sources.json with both fixed Preview HTTPS URLs.'
             ' Existing installations are NOT changed.')


def check_initial_sources_file(args):
    path = args.launch_source / 'defs/update/update_sources.json'
    try:
        payload = json.loads(path.read_text('utf-8-sig'))
    except (OSError, ValueError) as exc:
        fail('Cannot read fresh-install sources file: ' + str(path) + ': ' + str(exc))
    validate_initial_sources(args, payload, path)
    print('[OK] Fresh-install defaults point to fixed Preview feeds')


def check_initial_sources_archives(args):
    """Check shipped bytes, not merely the source config."""
    for file, entry in (
        (paths(args)['portable'], 'FRBLaunch/defs/update/update_sources.json'),
        (paths(args)['product'], 'system/defs/update/update_sources.json'),
    ):
        try:
            with zipfile.ZipFile(file) as archive:
                payload = json.loads(archive.read(entry).decode('utf-8-sig'))
        except (OSError, zipfile.BadZipFile, KeyError, UnicodeError, ValueError) as exc:
            fail('Cannot validate update URLs in ' + str(file) + '!' + entry + ': ' + str(exc))
        validate_initial_sources(args, payload, str(file) + '!' + entry)
    print('[OK] Portable and update ZIPs both ship the correct Preview feed URLs')


def gh_contents(args, name):
    endpoint = f'repos/{args.repo}/contents/release-feed/preview/{name}'
    result = gh(args, 'api', endpoint)
    if result.returncode:
        error = result.stderr + result.stdout
        if '404' in error or 'Not Found' in error:
            return None
        fail('Cannot inspect preview feed: ' + error.strip()[:500])
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or value.get('type') != 'file':
        fail('Preview channel path is not a file: ' + name)
    return value


def update_preview_file(args, name):
    contents = (args.stage / name).read_bytes()
    expected = json.loads(contents.decode('utf-8'))
    old = gh_contents(args, name)
    if old:
        try:
            previous_bytes = base64.b64decode(old.get('content', '').replace('\n', ''), validate=False)
            previous = json.loads(previous_bytes.decode('utf-8-sig'))
            existing_version = tuple(map(int, previous['version'].split('.')))
            target_version = tuple(map(int, expected['version'].split('.')))
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError('Cannot safely interpret current GitHub preview feed') from exc
        if existing_version > target_version:
            fail('Refusing to roll back GitHub preview channel: ' + name)
        if existing_version == target_version:
            if previous_bytes != contents:
                fail('Same-version preview feed differs; refusing overwrite: ' + name)
            print('[OK] Preview channel already matches: ' + name)
            return
    endpoint = f'repos/{args.repo}/contents/release-feed/preview/{name}'
    body = {
        'message': f'chore(release): preview {name} -> v{expected["version"]}',
        'content': base64.b64encode(contents).decode('ascii'),
        'branch': args.channel_branch,
    }
    if old:
        body['sha'] = old['sha']
    executable = shutil.which('gh')
    if not executable:fail('GitHub CLI missing')
    operation = subprocess.run([executable,'api',endpoint,'-X','PUT','--input','-'],
                               input=json.dumps(body).encode('utf-8'), capture_output=True)
    if operation.returncode:
        fail('Cannot update preview feed: '+operation.stderr.decode('utf-8','replace')[:500])
    print('[OK] Preview channel advanced: ' + name)


def check_preview_feed(args, retries=4):
    # GitHub raw responses may briefly be cached following a contents update.
    for attempt in range(retries):
        try:
            for name in ('updater_feed.json', 'product_feed.json'):
                request=urllib.request.Request(preview_feed_url(args, name),
                    headers={'User-Agent':'FRB-Launch-Preview-Feed-Check'})
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload=response.read(128*1024+1)
                    if response.status != 200 or len(payload)>128*1024:
                        fail('Preview channel inaccessible: ' + name)
                if json.loads(payload.decode('utf-8-sig')) != legacy.jsonfile(args.stage/name):
                    fail('Preview channel has not propagated yet: ' + name)
            print('[OK] Public fixed preview feed URLs match this release')
            return
        except (OSError,ValueError) as error:
            if attempt == retries-1: raise
            print('[RETRY] Waiting for GitHub raw preview feed propagation: '+str(error))
            time.sleep(3)


def advance_preview_channel(args):
    repo=gh_json(args,'api',f'repos/{args.repo}')
    if repo.get('default_branch') != args.channel_branch:
        fail('Channel branch differs from GitHub default branch: '+str(repo.get('default_branch')))
    # Publish updater information first. Product update discovery is last.
    update_preview_file(args,'updater_feed.json')
    update_preview_file(args,'product_feed.json')
    check_preview_feed(args)


def publish(args):
    validate_plan(args)
    if args.approved_tag!='v'+args.version:
        fail('Human approval required: --approved-tag v'+args.version)
    auth=gh(args,'auth','status')
    if auth.returncode:fail('gh not authenticated; run gh auth login')
    repo=gh_json(args,'repo','view',args.repo,'--json','nameWithOwner,isPrivate')
    if repo.get('isPrivate') or repo.get('nameWithOwner','').lower()!=args.repo.lower():
        fail('Public repository mismatch: '+args.repo)
    tag='v'+args.version
    found=gh(args,'api',f'repos/{args.repo}/releases/tags/{tag}')
    items=asset_files(args)
    if found.returncode:
        if '404' not in (found.stderr+found.stdout) and 'Not Found' not in (found.stderr+found.stdout):
            fail('Cannot inspect remote release: '+found.stderr.strip()[:500])
        print('[PUBLISH] Creating GitHub Pre-release '+tag)
        result=gh(args,'release','create',tag,*[str(x) for x in items],
                  '--repo',args.repo,'--title',f'FRB Launch {args.version} — Preview',
                  '--prerelease','--notes-file',str(args.stage/f'RELEASE_NOTES_{args.version}.md'))
        if result.returncode:fail('GitHub Release creation failed: '+result.stderr.strip()[:500])
    else:
        remote=json.loads(found.stdout)
        if not remote.get('prerelease') or remote.get('draft'):
            fail('Existing release is not a published Pre-release; refusing modification')
        byname={asset['name']:asset for asset in remote.get('assets',[])}
        expected={x.name for x in items}
        if set(byname)-expected:
            fail('Unexpected remote asset found; refusing modification')
        missing=[]
        for file in items:
            if file.name not in byname:
                missing.append(file)
                continue
            asset=byname[file.name]
            if asset.get('size')!=file.stat().st_size or asset.get('digest') != ('sha256:'+sha256(file)):
                fail('Existing GitHub asset differs or digest missing: '+file.name)
        if missing:
            result=gh(args,'release','upload',tag,*[str(x) for x in missing],'--repo',args.repo)
            if result.returncode:fail('GitHub asset upload failed: '+result.stderr.strip()[:500])
        else:
            print('[OK] All remote assets verified; no duplicate upload')
    legacy.online_check(args.stage,args.repo)
    advance_preview_channel(args)
    print('[OK] Published: https://github.com/'+args.repo+'/releases/tag/'+tag)


def configure_test(args):
    validate_plan(args)
    legacy.online_check(args.stage,args.repo)
    check_preview_feed(args)
    root=args.test_install.resolve()
    if root.name.lower()!='frblaunch' or root.parent.name.lower()!='frb_update_test':
        fail('Safety: test install must end in FRB_Update_Test/FRBLaunch')
    if not (root/'FRBLaunch.exe').is_file():fail('Test installation not found')
    current=legacy.jsonfile(root/'installed_release.json')
    if tuple(map(int,current['version'].split('.'))) >= tuple(map(int,args.version.split('.'))):
        fail('Test install is already equal/newer; no update necessary')
    # Check all Journal layouts. Never change a pending backup or journal.
    sys.path.insert(0,str(args.launch_source/'src'))
    from frb_update.updater_core import pending_recovery
    if pending_recovery(root):fail('Pending interrupted Journal; recover first')
    target=root/'UserConfig/update_sources.json'
    if target.is_symlink() or target.parent.is_symlink():fail('Symlinked config is not supported')
    desired={'schema':'frb-update-sources-v1',
             'updater_feed_url':preview_feed_url(args,'updater_feed.json'),
             'product_feed_url':preview_feed_url(args,'product_feed.json'),
             'allow_local_for_test':False}
    if target.exists() and legacy.jsonfile(target)==desired:
        print('[OK] TEST Feed already set to GitHub. No changes')
        return
    if target.exists():
        backup=target.with_name(target.name+'.before_'+args.version+'_'+
            datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid4().hex[:6]+'.bak')
        backup.write_bytes(target.read_bytes())
        print('[BACKUP] '+str(backup))
    legacy.atomic_json(target,desired)
    print('[OK] TEST Feed switched to GitHub; updater NOT launched')


def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['stage','verify','publish','configure-test'])
    p.add_argument('--version',required=True)
    p.add_argument('--launch-version',default='')
    p.add_argument('--studio-version',default='0.9.0')
    p.add_argument('--updater-version',default='')
    p.add_argument('--repo',default='tamasub/FRB-Launch')
    p.add_argument('--channel-branch',default='main')
    p.add_argument('--launch-source',type=Path,default=Path(__file__).resolve().parent.parent)
    p.add_argument('--studio-source',type=Path,default=Path('F:/FRB_Apps/FRB_Studio'))
    p.add_argument('--release-dir',type=Path,default=Path('F:/FRB_Apps/FRB_Release_Output'))
    p.add_argument('--test-install',type=Path,default=Path('F:/FRB_Update_Test/FRBLaunch'))
    p.add_argument('--notes',default='FRB Launch usability and updater improvements')
    p.add_argument('--approved-tag',default='')
    p.add_argument('--python',type=Path,default=Path(sys.executable))
    a=p.parse_args(argv)
    a.launch_source=a.launch_source.resolve()
    a.studio_source=a.studio_source.resolve()
    a.release_dir=a.release_dir.resolve()
    a.updater_version=a.updater_version or a.version
    require_version(a.version)
    legacy.repo_valid(a.repo)
    if not re.fullmatch(r'[A-Za-z0-9._-]+', a.channel_branch):
        fail('Invalid preview channel branch')
    a.stage=a.release_dir/('github_'+a.version)
    init_version(a)
    return a


def main(argv=None):
    try:
        a=parse_args(argv)
        if a.action=='stage':stage(a)
        elif a.action=='verify':validate_plan(a)
        elif a.action=='publish':publish(a)
        elif a.action=='configure-test':configure_test(a)
        return 0
    except Exception as exc:
        print('[ERROR] '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
