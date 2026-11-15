"""One-time, opt-in repair of the two authored Files Exp development roots.

Never touches the system install root, Studio user documents, or update Journal.
Backs up the entire user config before atomic replacement; only known item IDs
and new source-root variables are changed semantically.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

LAUNCH_ID = '3602dda2-b6e9-4a04-859e-56de69037470'
STUDIO_ID = 'studio_dir'
STUDIO_DATA_ID = 'f0628e81-c03f-4573-820c-4b56f8dcbe37'
STUDIO_COMMAND_ID = 'a9bf171f-68ba-46a9-a742-b47b7e529957'
ZIP_LAUNCH_IDS = {'launch_source_zip', '410f2fb3-fc02-471f-8d45-a338e6096461',
                  '7b24abcd-77ef-49c4-8fc6-bbc49c2729a8'}
ZIP_STUDIO_ID = 'zip_studio'
VAR_DEFINITIONS = (
    ('launch_source_root', 'Launchソースのフォルダー'),
    ('studio_source_root', 'Studioソースのフォルダー'),
)


def plan_repair(data: dict, launch_root: str, studio_root: str):
    if not isinstance(data, dict) or not isinstance(data.get('items'), list) or not isinstance(data.get('launch_variables'), list):
        raise ValueError('Launch JSONのitemsまたはlaunch_variablesが不正です')
    changes = []
    variables = data['launch_variables']
    for key, title in VAR_DEFINITIONS:
        value = launch_root if key.startswith('launch_') else studio_root
        existing = next((v for v in variables if v.get('variable_id') == key), None)
        if existing is None:
            variables.append(dict(variable_id=key, title=title,
                                  launch_variable_type='literal', launch_value=value,
                                  launch_date_offset_days=0, launch_date_format='', enabled=True))
            changes.append('変数追加: ' + key)
        elif existing.get('launch_value') != value:
            # Do not stomp a user's explicitly customized source-root variable.
            changes.append('変数は既存設定を保持: ' + key)

    wanted = {
        LAUNCH_ID: ('%launch_source_root%', '%launch_home%'),
        STUDIO_ID: ('%studio_source_root%', '%studio_root%'),
        STUDIO_DATA_ID: ('%studio_source_root%\\data\\json', '%studio_root%\\data\\json'),
    }
    for row in data['items']:
        ident = row.get('item_id')
        if ident in ZIP_LAUNCH_IDS:
            for action in row.get('launch_actions', ()):
                if action.get('launch_action_type') == 'Open' and (
                        action.get('launch_target') == '%launch_home%\\_make_launch_zip.bat'
                        or str(action.get('launch_target', '')).lower() ==
                        r'f:\frb_update_test\frblaunch\_make_launch_zip.bat'):
                    action['launch_target'] = '%launch_source_root%\\_make_launch_zip.bat'
                    changes.append(ident + ': ZIP作成先をLaunchソースに固定')
        elif ident == ZIP_STUDIO_ID:
            for action in row.get('launch_actions', ()):
                if action.get('launch_action_type') != 'Run':
                    continue
                original = action.get('launch_arguments', [])
                if isinstance(original, list):
                    updated = [arg.replace('%studio_root%\\cmd_make_FRBStudio_App_zip_v2.bat',
                                           '%studio_source_root%\\cmd_make_FRBStudio_App_zip_v2.bat')
                               if isinstance(arg, str) else arg for arg in original]
                    if updated != original:
                        action['launch_arguments'] = updated
                        changes.append(ident + ': ZIP実行先をStudioソースに固定')
                if action.get('launch_working_directory') == '%studio_root%':
                    action['launch_working_directory'] = '%studio_source_root%'
                    changes.append(ident + ': ZIP作業フォルダーをStudioソースに固定')
        if ident in wanted:
            expected, old = wanted[ident]
            original = row.get('launch_browse_target', '')
            if original == old or str(original).lower().startswith('f:\\frb_update_test\\'):
                row['launch_browse_target'] = expected
                changes.append(ident + ': Exp参照')
            for action in row.get('launch_actions', ()):
                if action.get('launch_action_type') != 'Open':
                    continue
                target = action.get('launch_target', '')
                expected_target = ('%studio_source_root%\\data' if ident == STUDIO_DATA_ID
                                   else expected)
                old_target = ('%studio_root%\\data' if ident == STUDIO_DATA_ID else old)
                if target == old_target or str(target).lower().startswith('f:\\frb_update_test\\'):
                    action['launch_target'] = expected_target
                    changes.append(ident + ': Open参照')
        if ident == STUDIO_COMMAND_ID:
            for action in row.get('launch_actions', ()):
                if action.get('launch_action_type') != 'Run':
                    continue
                program = str(action.get('launch_program', ''))
                if program.startswith('%studio_root%\\') or program.lower().startswith('f:\\frb_update_test\\'):
                    action['launch_program'] = '%studio_source_root%\\NativeShell\\_publish\\FRBStudio.NativeShell.exe'
                    changes.append(ident + ': Studio起動先')
                if action.get('launch_working_directory') == '%studio_root%' or str(action.get('launch_working_directory', '')).lower().startswith('f:\\frb_update_test\\'):
                    action['launch_working_directory'] = '%studio_source_root%'
                    changes.append(ident + ': 作業フォルダー')
    return changes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'FRBLaunch'
    parser.add_argument('--data', type=Path, default=base / 'UserData' / 'frb_launch_data.json')
    parser.add_argument('--launch-root', default=r'F:\FRB_Apps\FRB_Launch')
    parser.add_argument('--studio-root', default=r'F:\FRB_Apps\FRB_Studio')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if not args.data.is_file():
        parser.error('UserDataのLaunch JSONが見つかりません: ' + str(args.data))
    if args.data.is_symlink() or args.data.parent.is_symlink():
        parser.error('シンボリックリンク先のUserDataは編集しません')
    raw = args.data.read_bytes()
    data = json.loads(raw.decode('utf-8-sig'))
    changes = plan_repair(data, args.launch_root, args.studio_root)
    print('対象:', args.data)
    for change in changes:
        print('  ', change)
    if args.dry_run or not any('保持' not in c for c in changes):
        print('[DRY-RUN]' if args.dry_run else '[NO CHANGE]')
        return 0
    if os.name == 'nt':
        # Refuse to create inaccessible menu shortcuts.
        for target in (args.launch_root, args.studio_root):
            if not Path(target).is_dir():
                parser.error('フォルダーが存在しません。設定変更を中止: ' + target)
    backup_dir = args.data.parent / '_Backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / ('frb_launch_data.before_exp_fix_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:6] + '.json')
    with backup.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # Validate the serialized document before any replace.
    assert json.loads(payload) == data
    with tempfile.NamedTemporaryFile(dir=args.data.parent, prefix='.exp_fix_', suffix='.tmp', delete=False) as fp:
        temporary = Path(fp.name)
        try:
            fp.write(payload)
            fp.flush()
            os.fsync(fp.fileno())
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, args.data)
    finally:
        temporary.unlink(missing_ok=True)
    print('[OK] Config修正完了')
    print('[BACKUP]', backup)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
