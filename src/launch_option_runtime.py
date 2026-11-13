"""Thin Launch adapter for FRB Studio Family's ONE Node Composition Core.

No JSON merge rules live in Python. The packaged System settings stay unchanged.
Only when a User override exists do we ask the Studio-family Node CLI to
produce a temporary, full effective settings JSON for the existing Launch readers.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


EXPOSED_DATA_FILES = {
    'webview': 'webview_settings.json',
    'file_index': 'file_index_options.json',
}


def find_studio_root(launch_home, configured=None):
    candidates = [Path(configured)] if configured else []
    base = Path(launch_home)
    candidates.extend([base.parent / 'FRB_Studio', base / 'Studio', base])
    for directory in candidates:
        if (directory / 'tools' / 'option_settings' / 'cli.mjs').is_file():
            return directory
    return None


def find_node(launch_home, studio_root=None):
    base = Path(launch_home)
    candidates = [
        base / 'runtime' / 'node' / 'node.exe',
        base / 'runtime' / 'node.exe',
    ]
    if studio_root:
        candidates.extend([
            Path(studio_root) / 'runtime' / 'node' / 'node.exe',
            Path(studio_root) / 'tools' / 'change_core' / 'runtime' / 'node.exe',
        ])
    for exe in candidates:
        if exe.is_file():
            return str(exe)
    return shutil.which('node') or shutil.which('node.exe')


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
    if proc.returncode:
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
