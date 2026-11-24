"""Thin Launch adapter for FRB Studio Family's ONE Node Composition Core.

No JSON merge rules live in Python. The packaged System settings stay unchanged.
Only when a User override exists do we ask the Studio-family Node CLI to
produce a temporary, full effective settings JSON for the existing Launch readers.
"""
from __future__ import annotations

import os
import logging
import subprocess
from pathlib import Path
from runtime_paths import resolve_studio_cli, resolve_node


EXPOSED_DATA_FILES = {
    'webview': 'webview_settings.json',
    'file_index': 'file_index_options.json',
}


def find_studio_root(launch_home, configured=None):
    return resolve_studio_cli(launch_home, 'option_settings', configured)


def find_node(launch_home, studio_root=None):
    return resolve_node(launch_home, studio_root)


def effective_options_path(launch_home, state, id, *, configured_studio=None):
    """Return System path unless an explicit User JSON is present.

    A failed compose is NOT silently ignored: silently reverting to System
    defaults would discard the user's ownership choice in the running app.
    """
    if id not in EXPOSED_DATA_FILES:
        raise ValueError('Unknown option ID')
    name = EXPOSED_DATA_FILES[id]
    launch_home, state = Path(launch_home), Path(state)
    system = launch_home / 'config' / name
    user_root = state / 'UserConfig'
    if not (user_root / name).exists():
        return system
    studio = find_studio_root(launch_home, configured_studio)
    if studio is None:
        raise RuntimeError('Studio Family のOption Composerが見つかりません。')
    node = find_node(launch_home, studio)
    if node is None:
        raise RuntimeError('Node.js実行環境が見つかりません。配布用node.exeが必要です。')
    cmd = [node,str(studio/'tools'/'option_settings'/'cli.mjs'),
           '--id',id,'--studio-root',str(studio),
           '--system-root',str(launch_home/'config'),
           '--user-root',str(user_root)]
    proc = subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=15)
    logger = logging.getLogger('frb.launch.diagnostics')
    logger.info('Option Composer exit=%s id=%s', proc.returncode, id)
    if proc.returncode:
        logger.warning('Option Composer stderr: %s', proc.stderr.strip()[:2000])
        raise RuntimeError(f'Option Composer失敗: {proc.stderr.strip()}')
    runtime_dir = state / 'EffectiveOptions'
    runtime_dir.mkdir(parents=True,exist_ok=True)
    destination=runtime_dir/name
    tmp=runtime_dir/(name+'.tmp')
    try:
        tmp.write_text(proc.stdout,encoding='utf-8')
        os.replace(tmp,destination)
    finally:
        tmp.unlink(missing_ok=True)
    return destination
