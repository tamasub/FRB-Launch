"""FRB Launch 0284: migrate only obsolete *application* path references.

User config belongs to the user. This program is deliberately opt-in and never
ships a replacement config. By default it previews; --apply makes backed-up,
validated, atomic changes while FRBLaunch.exe is not running.

Launch paths:  F:\\FRB\\tools\\FRB_Launch -> %launch_home% (action/browse)
Studio paths:  F:\\FRB\\tools\\FRBStudio_App -> %studio_root% (action/browse)
Descriptions: new absolute local path for readability (no UI variable needed)
Index roots:  new absolute local Launch home (index only expands OS variables)
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from uuid import uuid4

LEGACY_LAUNCH = r'F:\FRB\tools\FRB_Launch'
LEGACY_STUDIO = r'F:\FRB\tools\FRBStudio_App'
LIVE_CONFIG = 'config/frb_launch_data.json'
INDEX_CONFIG = 'config/file_index_options.json'
PATH_FIELDS = ('launch_target', 'launch_browse_target', 'launch_program',
               'launch_working_directory')


def matching_suffix(value: str, legacy: str) -> str | None:
    """Only whole directory path and descendants; never a lookalike prefix."""
    if not isinstance(value, str):
        return None
    cleaned = value.replace('/', '\\')
    base = legacy.casefold()
    if cleaned.casefold() == base:
        return ''
    if cleaned.casefold().startswith(base + '\\'):
        return cleaned[len(legacy):]
    return None


def convert_path(value: str, *, launch_home: str, studio_home: str, symbolic: bool):
    for legacy, actual, token in (
        (LEGACY_LAUNCH, launch_home, '%launch_home%'),
        (LEGACY_STUDIO, studio_home, '%studio_root%'),
    ):
        suffix = matching_suffix(value, legacy)
        if suffix is not None:
            return (token if symbolic else actual) + suffix
    return value


def migrate_data(data, *, launch_home, studio_home):
    """Return a deep copy and a human-readable change log; never edit input."""
    if not isinstance(data, dict) or not isinstance(data.get('items'), list) or not isinstance(data.get('launch_variables'), list):
        raise ValueError('Launch JSONのitems/launch_variablesが正しくありません')
    converted = copy.deepcopy(data)
    changes = []

    def replace(owner, key, location, *, symbolic):
        before = owner.get(key)
        if not isinstance(before, str):
            return
        after = convert_path(before, launch_home=launch_home,
                             studio_home=studio_home, symbolic=symbolic)
        if before != after:
            owner[key] = after
            changes.append((location, before, after))

    for i, row in enumerate(converted['items']):
        if not isinstance(row, dict):
            raise ValueError('items内にオブジェクトでない項目があります')
        identity = f"items[{i}]({row.get('title', '')})"
        for field in PATH_FIELDS:
            replace(row, field, identity + '.' + field, symbolic=True)
        # Description is user-authored prose. Update ONLY when it exactly
        # duplicates one of this row's original operational targets.
        authored_paths = [row.get('launch_browse_target')]
        for original_action in row.get('launch_actions', []):
            if isinstance(original_action, dict):
                authored_paths.extend(original_action.get(field) for field in PATH_FIELDS)
        if row.get('description') in authored_paths and row.get('description'):
            replace(row, 'description', identity + '.description', symbolic=False)
        for j, action in enumerate(row.get('launch_actions', [])):
            if not isinstance(action, dict):
                raise ValueError('launch_actions内にオブジェクトでない項目があります')
            where = identity + f'.launch_actions[{j}]'
            for field in PATH_FIELDS:
                replace(action, field, where + '.' + field, symbolic=True)
            # launch_arguments are intentionally left alone; any changes to
            # free-form arguments require case-by-case review.

    for i, var in enumerate(converted['launch_variables']):
        if not isinstance(var, dict):
            raise ValueError('launch_variables内にオブジェクトでない項目があります')
        if var.get('variable_id') == 'studio_root' and var.get('launch_variable_type') == 'literal':
            replace(var, 'launch_value', f'launch_variables[{i}].studio_root.launch_value', symbolic=False)
    return converted, changes


def migrate_index(data, *, launch_home, studio_home):
    if not isinstance(data, dict) or not isinstance(data.get('index_folders'), list):
        raise ValueError('file_index_options.jsonのindex_foldersが正しくありません')
    converted = copy.deepcopy(data)
    changes = []
    for i, value in enumerate(data['index_folders']):
        if not isinstance(value, str):
            raise ValueError('index_foldersには文字列を指定してください')
        after = convert_path(value, launch_home=launch_home, studio_home=studio_home,
                             symbolic=False)
        if after != value:
            converted['index_folders'][i] = after
            changes.append((f'index_folders[{i}]', value, after))
    return converted, changes


def dump_json(original_bytes, updated):
    """Retain the existing JSON layout conventions and UTF-8 readable text."""
    has_bom = original_bytes.startswith(b'\xef\xbb\xbf')
    text = original_bytes.decode('utf-8-sig')
    indent = 2  # project configuration standard
    newline = '\r\n' if '\r\n' in text else '\n'
    ending = newline if text.endswith(('\r\n', '\n')) else ''
    return (b'\xef\xbb\xbf' if has_bom else b'') + (
        json.dumps(updated, ensure_ascii=False, indent=indent) + ending
    ).replace('\n', newline).encode('utf-8')


def app_is_running():
    """Fail safe on Windows when the actual running app could rewrite config."""
    if os.name != 'nt':
        return False
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq FRBLaunch.exe', '/FO', 'CSV', '/NH'],
                            capture_output=True, text=True, timeout=12)
    if result.returncode != 0:
        raise RuntimeError('Launchの起動状態が確認できません。停止後に再実行してください')
    return any(line.strip().strip('"').split('","')[0].casefold() == 'frblaunch.exe'
               for line in result.stdout.splitlines())


def prepare_files(home):
    launch = home / LIVE_CONFIG
    index = home / INDEX_CONFIG
    if not launch.is_file() or not index.is_file():
        raise FileNotFoundError(f'必要な設定ファイルがありません: {launch} / {index}')
    source = {}
    for path in (launch, index):
        raw = path.read_bytes()
        try:
            parsed = json.loads(raw.decode('utf-8-sig'))
        except (UnicodeError, json.JSONDecodeError) as e:
            raise ValueError(f'設定ファイルのJSONが不正です: {path}: {e}') from e
        source[path] = (raw, parsed)
    return source


def migrate(home, apply=False):
    home = home.resolve()
    launch_home = str(home)
    studio_home = str(home.parent / 'FRB_Studio')
    sources = prepare_files(home)
    path_config, path_index = (home / LIVE_CONFIG, home / INDEX_CONFIG)
    converted, changes = migrate_data(sources[path_config][1],
                                      launch_home=launch_home, studio_home=studio_home)
    index_conv, index_changes = migrate_index(sources[path_index][1],
                                              launch_home=launch_home, studio_home=studio_home)
    # Ensure the migrated Launch model remains valid according to the actual
    # Launch contract, before attempting to mutate user files.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
    try:
        from core import validate
        validate(converted)
    finally:
        sys.path.pop(0)
    planned = {path_config: (dump_json(sources[path_config][0], converted), changes),
               path_index: (dump_json(sources[path_index][0], index_conv), index_changes)}
    modified = {p: tup for p, tup in planned.items() if sources[p][0] != tup[0]}
    print('FRB Launch 0284 / 旧アプリパス移行')
    print('Launch:', launch_home)
    print('Studio:', studio_home)
    print('モード:', '適用' if apply else 'プレビュー（ファイルは変更しません）')
    for p in (path_config, path_index):
        print(f'  {p.relative_to(home)}: 変更 {len(planned[p][1])} 件')
        for loc, before, after in planned[p][1]:
            print(f'    {loc}\n      - {before}\n      + {after}')
    if not modified:
        print('差分なし。既に移行済みです。')
        return 0
    if not apply:
        print('\n変更には --apply を指定してください。')
        return 0
    if home.name.casefold() != 'frb_launch' or home.parent.name.casefold() != 'frb_apps':
        raise RuntimeError('移行先は FRB_Apps/FRB_Launch である必要があります。旧フォルダーで実行していないか確認してください')
    if not (home.parent / 'FRB_Studio').is_dir():
        raise RuntimeError('兄弟フォルダー FRB_Studio が見つかりません。移行先を確認してください')
    if app_is_running():
        raise RuntimeError('FRBLaunch.exe が起動中です。タスクトレイから完全終了して再実行してください')
    # Recheck the original bytes after all analyses / process checks.
    for p in sources:
        if p.read_bytes() != sources[p][0]:
            raise RuntimeError(f'処理中に設定が変更されました。作業を中断しました: {p}')
    backup = home / 'backups' / ('frb_apps_paths_0284_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:6])
    backup.mkdir(parents=True, exist_ok=False)
    # Backup BOTH live configs, even when only one currently needs migration.
    for p, (old, _) in sources.items():
        copy = backup / p.name
        with copy.open('xb') as f:
            f.write(old)
            f.flush()
            os.fsync(f.fileno())
    diff_lines = ['# FRB Launch 0284 — 移行差分', '', '旧環境の登録パスのみを更新。研究データ参照は維持。', '']
    for p in modified:
        before = sources[p][0].decode('utf-8-sig').splitlines(keepends=True)
        after = modified[p][0].decode('utf-8-sig').splitlines(keepends=True)
        diff_lines.extend(difflib.unified_diff(before, after,
                          fromfile=p.name + ' (backup)', tofile=p.name + ' (migrated)'))
    (backup / 'migration_diff.patch').write_text(''.join(diff_lines), encoding='utf-8')

    updated = []
    try:
        for p, (new, _) in modified.items():
            # Source integrity guarantee prevents accidentally overwriting a
            # user edit made between preview and commit.
            if p.read_bytes() != sources[p][0]:
                raise RuntimeError(f'他の操作による更新を検出しました: {p}')
            temp = p.with_name(p.name + '.0284_' + uuid4().hex[:8] + '.tmp')
            try:
                with temp.open('xb') as f:
                    f.write(new)
                    f.flush()
                    os.fsync(f.fileno())
                json.loads(temp.read_text('utf-8-sig'))
                os.replace(temp, p)
                updated.append(p)
            finally:
                temp.unlink(missing_ok=True)
    except Exception:
        for p in reversed(updated):
            # Roll back only after having verified the backup was written.
            restore = p.with_name(p.name + '.0284_rollback_' + uuid4().hex[:8] + '.tmp')
            try:
                with restore.open('xb') as fp:
                    fp.write((backup / p.name).read_bytes())
                    fp.flush()
                    os.fsync(fp.fileno())
                os.replace(restore, p)
            finally:
                restore.unlink(missing_ok=True)
        raise
    print('\n移行完了。旧データのバックアップと差分:', backup)
    print('※ 設定JSONの項目名やFRB研究データの参照先は変更していません。')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--apply', action='store_true', help='バックアップを取って変更を反映する（省略時プレビュー）')
    args = parser.parse_args(argv)
    try:
        return migrate(args.home, args.apply)
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
