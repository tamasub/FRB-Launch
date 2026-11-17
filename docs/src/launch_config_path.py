"""Stable Launch config name and lossless one-time migration of the old filename.

User-edited data, not the shipped default JSON, is the source of truth when
an existing Launch home is upgraded in place. No JSON fields are rewritten.
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

CONFIG_NAME = 'frb_launch_data.json'
LEGACY_CONFIG_NAME = 'frb_launch_sample_data_v0_1.json'
MIGRATION_MARKER = '.frb_launch_data_name_v1'


def _archive_config(root, paths):
    """Backup both possible versions before changing or deleting either one."""
    backup = Path(root) / 'backups' / (
        'config_filename_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:6]
    )
    backup.mkdir(parents=True, exist_ok=False)
    for path in paths:
        if path.is_file():
            shutil.copy2(path, backup / path.name)
    return backup


def _validate_json_bytes(contents, source):
    try:
        data = json.loads(contents.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Launch設定JSONが不正です: {source}: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'Launch設定JSONのルートがオブジェクトではありません: {source}')


def ensure_launch_config(home, *, user_root=None):
    if user_root is not None:
        return ensure_user_launch_config(home, user_root)

    """Return the canonical config; preserve a pre-existing legacy user's file.

    A full ZIP may already contain the new sample JSON next to the user's old
    JSON. On first upgrade the old JSON wins. A durable marker makes subsequent
    launches idempotent; older leftover files cannot replace the live config.
    """
    root = Path(home).resolve()
    config_dir = root / 'config'
    canonical = config_dir / CONFIG_NAME
    legacy = config_dir / LEGACY_CONFIG_NAME
    marker = config_dir / MIGRATION_MARKER
    if marker.is_file():
        if not canonical.is_file():
            raise RuntimeError('Launch設定が見つかりません: ' + str(canonical))
        return canonical
    if legacy.is_file():
        original = legacy.read_bytes()
        _validate_json_bytes(original, legacy)
        backup = _archive_config(root, (legacy, canonical))
        tmp = canonical.with_name(canonical.name + '.' + uuid4().hex + '.tmp')
        try:
            with tmp.open('xb') as fp:
                fp.write(original)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp, canonical)
            # Remove the obsolete live filename after it is safely archived.
            legacy.unlink()
            marker.write_text('Legacy JSON preserved in ' + str(backup) + '\n', encoding='utf-8')
        finally:
            tmp.unlink(missing_ok=True)
        return canonical
    if not canonical.is_file():
        raise RuntimeError('Launch設定が見つかりません: ' + str(canonical))
    _validate_json_bytes(canonical.read_bytes(), canonical)
    marker.write_text('Canonical FRB Launch config filename enabled.\n', encoding='utf-8')
    return canonical


# FRB Studio Family: User-owned Data JSON, independent of the installed program.
# The shipped template is an exact snapshot of the approved latest config. It
# is used only when neither an existing User JSON nor a legacy User JSON exists.
USER_DATA_DIR = 'UserData'
TEMPLATE_RELATIVE = Path('defaults') / 'frb_launch_data.template.json'


def ensure_user_launch_config(home, user_root):
    """Install the *current* user data once; never sync or overwrite it.

    Priority: existing AppData JSON > existing Launch config > template.
    Keep the original Launch/config JSON unchanged as a legacy recovery copy.
    All Studio and Launch writes must use the returned AppData path.
    """
    root = Path(home).resolve()
    dest = Path(user_root).resolve() / CONFIG_NAME
    if dest.exists():
        if not dest.is_file():
            raise RuntimeError('User Launch設定はファイルではありません: ' + str(dest))
        _validate_json_bytes(dest.read_bytes(), dest)
        return dest
    legacy = root / 'config' / LEGACY_CONFIG_NAME
    canonical = root / 'config' / CONFIG_NAME
    template = root / TEMPLATE_RELATIVE
    # The existing migration marker, when present, disambiguates an obsolete
    # legacy filename from the actual canonical user document.
    marker = root / 'config' / MIGRATION_MARKER
    source = (legacy if legacy.is_file() and not marker.is_file() else
              canonical if canonical.is_file() else
              legacy if legacy.is_file() else template)
    if not source.is_file():
        raise RuntimeError('Launch初期データが見つかりません: ' + str(template))
    content = source.read_bytes()
    _validate_json_bytes(content, source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation. On concurrent startup the first successful writer
    # wins, and a second process must never replace a user-edited document.
    try:
        with dest.open('xb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError:
        _validate_json_bytes(dest.read_bytes(), dest)
    return dest
