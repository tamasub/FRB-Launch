"""Independent full-ZIP system updater with guarded rollback and file ownership.

Never reads or writes UserData / UserConfig / AppData user settings. The single
allowed product is FRBLaunchIntegrated v1. The updater executable itself is
installed separately by bootstrap.py, and excluded from managed system files.
"""
from __future__ import annotations
import json
import os
import shutil
import stat
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from .contracts import (UpdateError, SHA256, MAX_ARCHIVE_SIZE, check_source,
                        download, safe_relative, sha256_file, version_tuple)

PACKAGE_SCHEMA = 'frb-system-package-v1'
STATE_FILE = 'installed_release.json'
MAX_PACKAGE_ENTRIES = 20000

def _no_reparse(root: Path, rel: Path):
    """Refuse Windows junctions and symlinks in the target path chain."""
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400) if path.exists() or path.is_symlink() else False:
            raise UpdateError('シンボリックリンク／ジャンクションへは更新しません: ' + str(path))

def _files(manifest: dict) -> dict[str,str]:
    if manifest.get('schema') != PACKAGE_SCHEMA or manifest.get('product') != 'FRBLaunchIntegrated':
        raise UpdateError('製品パッケージ形式が不正です')
    version_tuple(manifest.get('version'))
    files = manifest.get('files')
    if not isinstance(files, dict) or not files or len(files) > MAX_PACKAGE_ENTRIES:
        raise UpdateError('配布ファイル一覧が不正です')
    seen = set()
    for name, digest in files.items():
        safe_relative(name)
        if not SHA256.fullmatch(str(digest)):
            raise UpdateError('配布ファイルのSHA-256が不正です')
        key = name.casefold()
        if key in seen: raise UpdateError('大文字小文字だけが異なる配布ファイルが存在します')
        seen.add(key)
    if 'FRBLaunch.exe' not in files or 'Studio/NativeShell/_publish/FRBStudio.NativeShell.exe' not in files:
        raise UpdateError('Launch・Studioの両方を含む完全ZIPが必要です')
    return files

def validate_zip(archive: Path, *, expected_version: str | None = None) -> dict:
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) > MAX_PACKAGE_ENTRIES + 1:
            raise UpdateError('ZIPのエントリー数が多すぎます')
        if len(members) == 0 or sum(x.file_size for x in members) > MAX_ARCHIVE_SIZE * 2:
            raise UpdateError('ZIPの展開サイズが大きすぎます')
        if any((x.external_attr >> 16) & 0o170000 == stat.S_IFLNK for x in members):
            raise UpdateError('ZIPのシンボリックリンクは禁止です')
        if 'release.json' not in z.namelist():
            raise UpdateError('release.jsonがありません')
        info = z.getinfo('release.json')
        if info.file_size > 512 * 1024: raise UpdateError('release.jsonが大きすぎます')
        manifest = json.loads(z.read(info).decode('utf-8-sig'))
        files = _files(manifest)
        if expected_version and manifest['version'] != expected_version:
            raise UpdateError('公開バージョンとZIPのバージョンが一致しません')
        expected = {'release.json'} | {'system/'+rel for rel in files}
        if set(z.namelist()) != expected or len(z.namelist()) != len(expected):
            raise UpdateError('ZIP内容がrelease.jsonのファイル一覧と異なります')
        for name,digest in files.items():
            entry = z.getinfo('system/'+name)
            if entry.is_dir(): raise UpdateError('ファイル指定の場所がフォルダーです')
            import hashlib
            value = hashlib.sha256()
            with z.open(entry) as fp:
                for chunk in iter(lambda: fp.read(1024*1024), b''):
                    value.update(chunk)
            if value.hexdigest().lower() != digest.lower():
                raise UpdateError('ZIP内ファイルのSHA-256が不正です: '+name)
        return manifest

def _existing_state(root: Path):
    file = root / STATE_FILE
    if not file.exists(): return None
    obj = json.loads(file.read_text('utf-8-sig'))
    _files(obj)
    return obj

def _restore(root: Path, folder: Path):
    journal = json.loads((folder/'journal.json').read_text('utf-8'))
    for relname in journal['touched']:
        path = root / safe_relative(relname)
        _no_reparse(root, safe_relative(relname))
        backup = folder/'files'/safe_relative(relname)
        if backup.is_file():
            path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(backup, path)
        elif path.is_file():
            path.unlink()
    state_backup = folder/'old_installed_release.json'
    if state_backup.is_file():
        shutil.copy2(state_backup, root/STATE_FILE)
    else:
        (root/STATE_FILE).unlink(missing_ok=True)
    journal['phase']='rolled_back'
    (folder/'journal.json').write_text(json.dumps(journal,indent=2)+'\n','utf-8')

def recover_interrupted(root: Path):
    backups = root.parent / ('.'+root.name+'_update_backups')
    for folder in sorted(backups.glob('*')) if backups.is_dir() else ():
        journal = folder/'journal.json'
        if journal.is_file():
            obj=json.loads(journal.read_text('utf-8'))
            if obj['phase']=='applying':
                _restore(root,folder)

def install_zip(archive: Path, install_root: Path, *, expected_version: str | None = None,
                fault_after: int | None = None):
    """Apply approved system files; rollback on error. `fault_after` is a test hook."""
    root = Path(install_root).resolve()
    if not (root/'FRBLaunch.exe').is_file():
        raise UpdateError('配布用FRBLaunch.exeのあるフォルダーを指定してください')
    if root.is_symlink(): raise UpdateError('インストール先がシンボリックリンクです')
    manifest = validate_zip(archive, expected_version=expected_version)
    recover_interrupted(root)
    old=_existing_state(root)
    if old and version_tuple(manifest['version']) <= version_tuple(old['version']):
        raise UpdateError('同一版・旧版への更新は行いません')
    new_files=_files(manifest)
    old_files=set(_files(old)) if old else set()
    touched=sorted(set(new_files) | (old_files-set(new_files)))
    for name in touched: _no_reparse(root,safe_relative(name))
    backups = root.parent / ('.'+root.name+'_update_backups')
    backups.mkdir(parents=True,exist_ok=True)
    folder = backups/(time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    folder.mkdir()
    journal={'schema':'frb-update-journal-v1','phase':'preparing',
             'old_version':old['version'] if old else None,'new_version':manifest['version'],
             'touched':touched}
    (folder/'journal.json').write_text(json.dumps(journal,indent=2)+'\n','utf-8')
    for name in touched:
        path = root/safe_relative(name)
        if path.is_file():
            target=folder/'files'/safe_relative(name)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
    if (root/STATE_FILE).is_file():
        shutil.copy2(root/STATE_FILE,folder/'old_installed_release.json')
    with tempfile.TemporaryDirectory(prefix='.frb_update_stage_',dir=root.parent) as staging_name:
        staging=Path(staging_name)
        with zipfile.ZipFile(archive) as z:
            for rel,digest in new_files.items():
                target=staging/safe_relative(rel)
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open('system/'+rel) as source, target.open('wb') as dest:
                    shutil.copyfileobj(source,dest,1024*1024)
                if sha256_file(target).lower()!=digest.lower():
                    raise UpdateError('展開後のSHA-256不一致: '+rel)
        journal['phase']='applying'
        (folder/'journal.json').write_text(json.dumps(journal,indent=2)+'\n','utf-8')
        counter=0
        try:
            for rel in touched:
                path=root/safe_relative(rel)
                if rel in new_files:
                    path.parent.mkdir(parents=True,exist_ok=True)
                    os.replace(staging/safe_relative(rel),path)
                elif path.is_file():
                    path.unlink()  # remove ONLY old release-owned files
                counter+=1
                if fault_after is not None and counter >= fault_after:
                    raise OSError('simulated write failure')
            temp=root/(STATE_FILE+'.tmp')
            temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
            os.replace(temp,root/STATE_FILE)
            journal['phase']='completed'
            (folder/'journal.json').write_text(json.dumps(journal,indent=2)+'\n','utf-8')
            return folder
        except BaseException:
            _restore(root,folder)
            raise

def wait_for_pid(pid: int, timeout: float=90):
    if pid <= 0: return
    if os.name=='nt':
        import ctypes
        kernel=ctypes.windll.kernel32
        SYNCHRONIZE=0x00100000
        handle=kernel.OpenProcess(SYNCHRONIZE,False,pid)
        if handle:
            try:
                if kernel.WaitForSingleObject(handle,int(timeout*1000)) != 0:
                    raise UpdateError('Launchの終了を確認できません')
            finally:
                kernel.CloseHandle(handle)
        return
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try: os.kill(pid,0)
        except ProcessLookupError: return
        time.sleep(.2)
    raise UpdateError('Launchの終了を確認できません')

def ensure_programs_closed(timeout: int=90):
    if os.name!='nt': return
    import subprocess
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        proc=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,errors='replace',timeout=15)
        output=proc.stdout.lower()
        if ('"frblaunch.exe"' not in output and '"frbstudio.nativeshell.exe"' not in output):
            return
        time.sleep(.7)
    raise UpdateError('LaunchまたはStudioが起動中です。終了してから更新してください')

def apply_request(request_path: Path, install_root: Path, *, allow_local=False):
    obj=json.loads(Path(request_path).read_text('utf-8-sig'))
    if obj.get('schema')!='frb-update-request-v1':
        raise UpdateError('更新要求の形式が不正です')
    # `allow_local` is a CLI opt-in; a downloaded/request JSON cannot grant it.
    check_source(obj.get('archive_url',''),allow_local=allow_local)
    version_tuple(obj.get('version'))
    with tempfile.TemporaryDirectory(prefix='.frb_download_',dir=Path(install_root).resolve().parent) as temp:
        archive=download(obj['archive_url'],Path(temp)/'release.zip',digest=obj['sha256'],
                         size=obj['size'],allow_local=allow_local)
        package=validate_zip(archive,expected_version=obj['version'])
        if package.get('components') != obj.get('components'):
            raise UpdateError('配布情報とZIPのコンポーネントバージョンが一致しません')
        return install_zip(archive,install_root,expected_version=obj['version'])
