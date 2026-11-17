"""Independent full-ZIP system updater with guarded rollback and file ownership.

Never reads or writes UserData / UserConfig / AppData user settings. The single
allowed product is FRBLaunchIntegrated v1. The updater executable itself is
installed separately by bootstrap.py, and excluded from managed system files.
"""
from __future__ import annotations
import json
import os
import contextlib
import hashlib
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
# The full Launch + Studio distribution includes thousands of DLLs and assets.
# release.json contains a SHA-256 entry for each file. 512 KiB is too small
# for real installations; keep an explicit, bounded 8 MiB safety limit.
# This is separate from the much smaller web feed JSON (128 KiB).
MAX_RELEASE_MANIFEST_SIZE = 8 * 1024 * 1024

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

def _progress(callback, phase: str, message: str, current=None, total=None):
    """Report observable stages without making GUI a core dependency."""
    if callback is not None:
        callback(phase, message, current, total)


def _write_journal(folder: Path, journal: dict):
    target = folder / 'journal.json'
    temp = folder / 'journal.json.tmp'
    temp.write_text(json.dumps(journal, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    os.replace(temp, target)


def _same_content(a: Path, b: Path) -> bool:
    return (a.is_file() and b.is_file() and a.stat().st_size == b.stat().st_size
            and sha256_file(a) == sha256_file(b))


@contextlib.contextmanager
def update_lock(root: Path):
    """Process-scoped exclusive update lock, independent of the app install."""
    root = Path(root).resolve()
    key = __import__('hashlib').sha256(str(root).casefold().encode('utf-8')).hexdigest()[:20]
    path = root.parent / ('.frb_updater_' + key + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() < 1:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise UpdateError('別のUpdaterが更新／復旧を実行中です') from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise UpdateError('別のUpdaterが更新／復旧を実行中です') from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_zip(archive: Path, *, expected_version: str | None = None, progress=None) -> dict:
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
        if info.file_size > MAX_RELEASE_MANIFEST_SIZE:
            raise UpdateError(f'release.jsonが大きすぎます ({info.file_size:,} bytes / 上限 {MAX_RELEASE_MANIFEST_SIZE:,} bytes)')
        manifest = json.loads(z.read(info).decode('utf-8-sig'))
        files = _files(manifest)
        if expected_version and manifest['version'] != expected_version:
            raise UpdateError('公開バージョンとZIPのバージョンが一致しません')
        expected = {'release.json'} | {'system/'+rel for rel in files}
        if set(z.namelist()) != expected or len(z.namelist()) != len(expected):
            raise UpdateError('ZIP内容がrelease.jsonのファイル一覧と異なります')
        total=len(files)
        _progress(progress,'verify','更新ZIPの内容とSHA-256を確認しています',0,total)
        for index,(name,digest) in enumerate(files.items(),1):
            entry = z.getinfo('system/'+name)
            if entry.is_dir(): raise UpdateError('ファイル指定の場所がフォルダーです')
            import hashlib
            value = hashlib.sha256()
            with z.open(entry) as fp:
                for chunk in iter(lambda: fp.read(1024*1024), b''):
                    value.update(chunk)
            if value.hexdigest().lower() != digest.lower():
                raise UpdateError('ZIP内ファイルのSHA-256が不正です: '+name)
            if index % 50 == 0 or index == total:
                _progress(progress,'verify',f'更新ZIPを検証中 ({index:,}/{total:,})',index,total)
        return manifest

def _existing_state(root: Path):
    file = root / STATE_FILE
    if not file.exists(): return None
    obj = json.loads(file.read_text('utf-8-sig'))
    _files(obj)
    return obj

def _retry_locked_file(action, target: Path, *, attempts: int = 12, interval: float = 0.5):
    """Retry sharing errors; WinError 5 only for Windows executable files.

    A transient access denied is common while antivirus scans a new EXE.
    A permanent ACL denial remains an error, with the target path reported.
    """
    for attempt in range(attempts):
        try:
            return action()
        except OSError as exc:
            code = getattr(exc, 'winerror', None)
            retryable = code in (32, 33) or (code == 5 and Path(target).suffix.lower()
                                              in {'.exe', '.dll', '.pyd'})
            if not retryable:
                raise
            if attempt == attempts - 1:
                raise UpdateError(
                    f'更新／復旧先のファイルが使用中またはアクセス拒否: {target} '
                    f'(WinError {code}、{attempts}回再試行後も失敗)'
                ) from exc
            time.sleep(interval)


def _atomic_restore_file(source: Path, target: Path):
    """Prepare bytes beside target and atomically replace; never truncate live EXEs."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix='.frb_restore_', suffix='.tmp', dir=target.parent)
    os.close(fd)
    temporary = Path(filename)
    try:
        shutil.copy2(source, temporary)
        _retry_locked_file(lambda: os.replace(temporary, target), target)
    finally:
        temporary.unlink(missing_ok=True)



def legacy_backup_root(root: Path) -> Path:
    """Original backup directory, preserved for rollback of older updates."""
    root = Path(root).resolve()
    return root.parent / ('.' + root.name + '_update_backups')


def backup_root(root: Path) -> Path:
    """Per-install update backups in the user's LocalAppData on Windows.

    A stable hash prevents two installs with the same folder name from sharing
    journals. On non-Windows test hosts without LOCALAPPDATA, retain the prior
    location to keep temporary test fixtures self-contained.
    """
    root = Path(root).resolve()
    localappdata = os.environ.get('LOCALAPPDATA')
    if not localappdata:
        if os.name == 'nt':
            raise UpdateError('LOCALAPPDATAが取得できないため、安全なバックアップ先を決定できません')
        return legacy_backup_root(root)
    identifier = hashlib.sha256(str(root).casefold().encode('utf-8')).hexdigest()[:16]
    return Path(localappdata).resolve() / 'FRBLaunch' / 'UpdateBackups' / (root.name + '_' + identifier)


def backup_roots_for_recovery(root: Path) -> tuple[Path, ...]:
    """Read both old and new layouts; never silently drop a pending Journal."""
    legacy = legacy_backup_root(root)
    modern = backup_root(root)
    return (legacy,) if modern == legacy else (legacy, modern)


def iter_backup_journals(root: Path):
    for backups in backup_roots_for_recovery(root):
        if backups.is_dir():
            for folder in sorted(backups.iterdir()):
                if folder.is_dir():
                    journal = folder / 'journal.json'
                    if journal.is_file():
                        yield folder, journal


def pending_recovery(root: Path) -> bool:
    """True if rollback remains incomplete; app restart would lock its files."""
    root = Path(root).resolve()
    for folder, journal in iter_backup_journals(root):
        try:
            if json.loads(journal.read_text('utf-8')).get('phase') == 'applying':
                return True
        except (OSError, ValueError, TypeError):
            # Malformed journal must be inspected before launching the app.
            return True
    return False


def _restore(root: Path, folder: Path, *, progress=None):
    journal = json.loads((folder/'journal.json').read_text('utf-8'))
    touched = journal['touched']
    total=len(touched)
    _progress(progress,'rollback','旧版を復元しています',0,total)
    for index, relname in enumerate(touched,1):
        rel=safe_relative(relname)
        path = root / rel
        _no_reparse(root, rel)
        backup = folder/'files'/rel
        if backup.is_file():
            # Older journals list every *planned* file, not just files changed.
            # Writing unchanged EXEs during recovery caused WinError 32.
            if not _same_content(path, backup):
                _atomic_restore_file(backup, path)
        elif path.is_file():
            _retry_locked_file(path.unlink, path)
        if index % 50 == 0 or index == total:
            _progress(progress,'rollback',f'旧版を復元中 ({index:,}/{total:,})',index,total)
    state_backup = folder/'old_installed_release.json'
    state = root / STATE_FILE
    if state_backup.is_file():
        if not _same_content(state,state_backup):
            _atomic_restore_file(state_backup,state)
    elif state.is_file():
        _retry_locked_file(state.unlink,state)
    journal['phase']='rolled_back'
    _write_journal(folder, journal)


def recover_interrupted(root: Path, *, progress=None):
    for folder, journal in iter_backup_journals(root):
        obj = json.loads(journal.read_text('utf-8'))
        if obj.get('phase') == 'applying':
            _progress(progress, 'rollback', f'中断Journalを復旧: {folder.name}')
            _restore(root, folder, progress=progress)


def install_zip(archive: Path, install_root: Path, *, expected_version: str | None = None,
                fault_after: int | None = None, progress=None):
    """Apply approved system files; rollback on error. `fault_after` is a test hook."""
    root = Path(install_root).resolve()
    if not (root/'FRBLaunch.exe').is_file():
        raise UpdateError('配布用FRBLaunch.exeのあるフォルダーを指定してください')
    if root.is_symlink(): raise UpdateError('インストール先がシンボリックリンクです')
    # Recover before the next update. A pending rollback must not be discarded.
    recover_interrupted(root, progress=progress)
    if pending_recovery(root):
        raise UpdateError('以前の更新が復旧未完了です')
    old = _existing_state(root)
    manifest = validate_zip(archive, expected_version=expected_version,progress=progress)
    if old and version_tuple(manifest['version']) <= version_tuple(old['version']):
        raise UpdateError('同一版・旧版への更新は行いません')
    new_files=_files(manifest)
    old_files=set(_files(old)) if old else set()
    touched=sorted(set(new_files) | (old_files-set(new_files)))
    for name in touched: _no_reparse(root,safe_relative(name))
    backups = backup_root(root)
    backups.mkdir(parents=True, exist_ok=True)
    # New Windows backups use LocalAppData, often on C: even when the app is
    # installed on F:. Fail before writing a Journal if that volume is too full.
    backup_bytes = sum((root / safe_relative(name)).stat().st_size for name in touched
                       if (root / safe_relative(name)).is_file())
    free_bytes = shutil.disk_usage(backups).free
    if free_bytes < backup_bytes + 32 * 1024 * 1024:
        raise UpdateError('バックアップ先の空き容量が不足しています: '
                          + str(backups) + f' (必要約{backup_bytes:,} bytes + 32 MiB)')
    folder = backups/(time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    folder.mkdir()
    journal={'schema':'frb-update-journal-v1','phase':'preparing',
             'old_version':old['version'] if old else None,'new_version':manifest['version'],
             'touched':touched}
    _write_journal(folder,journal)
    total=len(touched)
    _progress(progress,'backup','旧Systemファイルをバックアップしています',0,total)
    for index,name in enumerate(touched,1):
        path = root/safe_relative(name)
        if path.is_file():
            target=folder/'files'/safe_relative(name)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
        if index % 50 == 0 or index == total:
            _progress(progress,'backup',f'バックアップ中 ({index:,}/{total:,})',index,total)
    if (root/STATE_FILE).is_file():
        shutil.copy2(root/STATE_FILE,folder/'old_installed_release.json')
    with tempfile.TemporaryDirectory(prefix='.frb_update_stage_',dir=root.parent) as staging_name:
        staging=Path(staging_name)
        _progress(progress,'stage','更新ファイルを一時領域へ展開しています',0,len(new_files))
        with zipfile.ZipFile(archive) as z:
            for index,(rel,digest) in enumerate(new_files.items(),1):
                target=staging/safe_relative(rel)
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open('system/'+rel) as source, target.open('wb') as dest:
                    shutil.copyfileobj(source,dest,1024*1024)
                if sha256_file(target).lower()!=digest.lower():
                    raise UpdateError('展開後のSHA-256不一致: '+rel)
                if index % 50 == 0 or index == len(new_files):
                    _progress(progress,'stage',f'更新ファイルを展開中 ({index:,}/{len(new_files):,})',index,len(new_files))
        journal['phase']='applying'
        _write_journal(folder,journal)
        counter=0
        changed=0
        try:
            _progress(progress,'apply','新しいSystemファイルを適用しています',0,total)
            for index,rel in enumerate(touched,1):
                path=root/safe_relative(rel)
                if rel in new_files:
                    # A release number may change while the binary is identical.
                    # Replacing an unchanged running EXE is unnecessary and risky.
                    if not (path.is_file() and sha256_file(path).lower()==new_files[rel].lower()):
                        path.parent.mkdir(parents=True,exist_ok=True)
                        _retry_locked_file(lambda: os.replace(staging/safe_relative(rel), path), path)
                        changed+=1
                elif path.is_file():
                    _retry_locked_file(path.unlink, path)
                    changed+=1
                counter+=1
                if index % 50 == 0 or index == total:
                    _progress(progress,'apply',f'System適用中 ({index:,}/{total:,}、変更{changed:,}件)',index,total)
                if fault_after is not None and counter >= fault_after:
                    raise OSError('simulated write failure')
            temp=root/(STATE_FILE+'.tmp')
            temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
            _retry_locked_file(lambda: os.replace(temp, root/STATE_FILE), root/STATE_FILE)
            _progress(progress,'verify_installed','適用後のSystemファイルを検証しています',0,len(new_files))
            for index,(rel,digest) in enumerate(new_files.items(),1):
                target=root/safe_relative(rel)
                if not target.is_file() or sha256_file(target).lower()!=digest.lower():
                    raise UpdateError('適用後のSHA-256が一致しません: '+rel)
                if index % 50 == 0 or index == len(new_files):
                    _progress(progress,'verify_installed',
                              f'適用後の整合性を確認中 ({index:,}/{len(new_files):,})',
                              index,len(new_files))
            journal['phase']='completed'
            _write_journal(folder,journal)
            _progress(progress,'completed',f'更新ファイル適用完了（実変更 {changed:,}件）',total,total)
            return folder
        except BaseException as original:
            try:
                _restore(root, folder,progress=progress)
            except Exception as recovery_error:
                raise UpdateError(
                    '更新に失敗し、旧版の復旧も未完了です。'
                    'Launchを起動せず、他のLaunch／Studioを閉じてから再試行してください。'
                    f' 元のエラー: {original}; 復旧エラー: {recovery_error}'
                ) from recovery_error
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
        if proc.returncode != 0:
            raise UpdateError('起動中プロセスの確認に失敗しました: tasklist')
        output=proc.stdout.lower()
        if ('"frblaunch.exe"' not in output and '"frbstudio.nativeshell.exe"' not in output):
            return
        time.sleep(.7)
    raise UpdateError('LaunchまたはStudioが起動中です。終了してから更新してください')

def apply_request(request_path: Path, install_root: Path, *, allow_local=False, progress=None):
    obj=json.loads(Path(request_path).read_text('utf-8-sig'))
    if obj.get('schema')!='frb-update-request-v1':
        raise UpdateError('更新要求の形式が不正です')
    # `allow_local` is a CLI opt-in; a downloaded/request JSON cannot grant it.
    check_source(obj.get('archive_url',''),allow_local=allow_local)
    version_tuple(obj.get('version'))
    _progress(progress,'download','更新ZIPを取得しています')
    with tempfile.TemporaryDirectory(prefix='.frb_download_',dir=Path(install_root).resolve().parent) as temp:
        archive=download(obj['archive_url'],Path(temp)/'release.zip',digest=obj['sha256'],
                         size=obj['size'],allow_local=allow_local,
                         progress=lambda current,total: _progress(
                             progress,'download',f'更新ZIPを取得中 ({current:,}/{total:,} bytes)',current,total))
        _progress(progress,'download','更新ZIPの取得が完了しました')
        package=validate_zip(archive,expected_version=obj['version'],progress=progress)
        if package.get('components') != obj.get('components'):
            raise UpdateError('配布情報とZIPのコンポーネントバージョンが一致しません')
        return install_zip(archive,install_root,expected_version=obj['version'],progress=progress)
