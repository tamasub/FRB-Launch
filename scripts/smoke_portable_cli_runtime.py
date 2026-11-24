"""Run against an EXTRACTED portable release on Windows; no real user data writes.
Usage: python scripts/smoke_portable_cli_runtime.py --home C:\\Temp\\FRBLaunch
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from launch_menu_registration import (studio_core_root, records_for_sources, commit_add,
    read_item_for_edit, prepare_update, commit_update, prepare_delete, commit_delete)
from launch_option_runtime import effective_options_path, find_node
from runtime_paths import portable_runtime


def require(condition, message):
    if not condition:
        raise RuntimeError(message)
    print('PASS:', message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', required=True, type=Path)
    home = parser.parse_args().home.resolve()
    if os.name != 'nt':
        raise SystemExit('Windows portable binaries required')
    if not portable_runtime(home):
        raise SystemExit('Extracted release with installed_release.json required')
    os.environ['PATH'] = os.pathsep.join(str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / p) for p in ('System32', ''))
    os.environ.pop('FRB_LAUNCH_NODE', None)
    os.environ['FRB_LAUNCH_HOME'] = str(home)
    with tempfile.TemporaryDirectory(prefix='frb_portable_smoke_') as directory:
        base = Path(directory)
        os.chdir(home)
        require(not shutil.which('node') and not shutil.which('node.exe'), 'No external Node on PATH')
        studio = studio_core_root(home)
        require(studio == (home / 'Studio').resolve(), 'Bundled Studio selected')
        node = Path(find_node(home, studio) or '.')
        require(node in ((home / 'runtime/node/node.exe').resolve(), (studio / 'runtime/node/node.exe').resolve()), 'Bundled Node selected: ' + str(node))
        state = base / 'FRBLaunch'
        config = state / 'UserData/frb_launch_data.json'
        config.parent.mkdir(parents=True)
        shutil.copyfile(home / 'defaults/frb_launch_data.template.json', config)
        folder = base / 'Portable CLI Smoke Folder'
        folder.mkdir()
        title = folder.name
        result = commit_add(config, studio, 'system', 'folders', records_for_sources([{'kind':'directory', 'value':str(folder), 'title':title}]))
        require(result['status'] == 'COMMITTED', 'Folder registration via Change Core')
        rows = json.loads(config.read_text(encoding='utf-8-sig'))['items']
        row = next(r for r in rows if r.get('title') == title and r.get('launch_browse_target') == str(folder))
        item, sha = read_item_for_edit(config, 'system', row['item_id'])
        plan = prepare_update(config, studio, 'system', item['item_id'], [{'path':'title','value':title+' edited'}], base_sha256=sha)
        require(commit_update(plan)['status'] == 'COMMITTED', 'Menu edit via Change Core')
        plan = prepare_delete(config, studio, 'system', item['item_id'])
        require(commit_delete(plan)['status'] == 'COMMITTED', 'Menu deletion via Change Core')
        require(folder.is_dir(), 'Physical folder untouched')
        user = state / 'UserConfig'
        user.mkdir()
        (user / 'webview_settings.json').write_text('{"remember_login":false}', encoding='utf-8')
        effective = effective_options_path(home, state, 'webview')
        require(json.loads(effective.read_text(encoding='utf-8'))['remember_login'] is False, 'Option Composer via bundled Node')
        os.chdir(home)


if __name__ == '__main__':
    main()
