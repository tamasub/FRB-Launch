"""Single-template FRB Launch reset; reuses the existing backup BAT.

No secondary backup implementation is created here. The verified ZIP is
created solely by backup_frb_launch_config_log.bat (Backup-FrbLaunch.ps1).
Only the one UserData/frb_launch_data.json document is ever replaced.
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from launch_config_path import CONFIG_NAME, TEMPLATE_RELATIVE, _validate_json_bytes

BACKUP_ENTRY = 'user_data/UserData/frb_launch_data.json'


def reset_launch_data(launch_home, state_dir, *, run_backup=None):
    """Replace the user document with exact approved template bytes.

    The existing backup command must succeed and its newly produced archive
    must contain a byte-identical pre-reset document. Errors leave UserData
    unchanged; no template is applied without a verified pre-reset snapshot.
    """
    home = Path(launch_home).resolve()
    state = Path(state_dir).resolve()
    user = state / 'UserData' / CONFIG_NAME
    template = home / TEMPLATE_RELATIVE
    script = home / 'backup_frb_launch_config_log.bat'
    if not user.is_file():
        raise FileNotFoundError('User設定JSONが見つかりません: ' + str(user))
    old = user.read_bytes()
    _validate_json_bytes(old, user)
    if not template.is_file():
        raise FileNotFoundError('初期化テンプレートがありません: ' + str(template))
    fresh = template.read_bytes()
    _validate_json_bytes(fresh, template)
    if not script.is_file():
        raise FileNotFoundError('既存バックアップBATがありません: ' + str(script))

    backup_dir = state / '_Backups'
    known = {p.name for p in backup_dir.glob('FRBLaunch_Backup_*.zip')} if backup_dir.is_dir() else set()
    if run_backup is None:
        def run_backup():
            result = subprocess.run(['cmd.exe', '/d', '/c', str(script)],
                                    cwd=str(home), capture_output=True,
                                    timeout=180)
            if result.returncode != 0:
                raise RuntimeError('既存バックアップBATが失敗しました。初期化を中止しました。終了コード: '
                                   + str(result.returncode))
    run_backup()

    created = sorted((p for p in backup_dir.glob('FRBLaunch_Backup_*.zip')
                      if p.is_file() and p.name not in known),
                     key=lambda p: p.stat().st_mtime_ns, reverse=True)
    if len(created) != 1:
        raise RuntimeError('新規バックアップZIPを一意に特定できません。初期化を中止しました。')
    try:
        with ZipFile(created[0]) as archive:
            if archive.read(BACKUP_ENTRY) != old:
                raise RuntimeError('バックアップと現在のUser設定が一致しません。初期化を中止しました。')
    except (BadZipFile, KeyError) as exc:
        raise RuntimeError('バックアップZIPに対象のUser設定がありません。初期化を中止しました。') from exc

    # Share ChangeSet's cooperative lock: a concurrent Node ChangeSet cannot
    # commit while the final snapshot is checked and replaced. Studio should
    # be closed for reset because legacy GUI writes may not honor this lock.
    lock_path = user.with_name(user.name + '.studio-changeset.lock')
    tmp = user.with_name('.' + user.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        lock = lock_path.open('xb')
    except FileExistsError as exc:
        raise RuntimeError('設定JSONを別の処理が更新中です。初期化を中止しました。') from exc
    try:
        with lock:
            if user.read_bytes() != old:
                raise RuntimeError('バックアップ中にStudioが設定を更新しました。初期化を中止しました。')
            with tmp.open('xb') as output:
                output.write(fresh)
                output.flush()
                os.fsync(output.fileno())
            os.replace(tmp, user)
    finally:
        tmp.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)
    return created[0]
