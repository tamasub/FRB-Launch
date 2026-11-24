"""Locate editable files independently of PyInstaller's build output."""
import json
from pathlib import Path
from launch_config_path import CONFIG_NAME, LEGACY_CONFIG_NAME


def launch_home(binary_root):
    root=Path(binary_root).resolve()
    marker=root/'launch_home.json'
    if not marker.exists():return root
    relative=json.loads(marker.read_text(encoding='utf-8'))['launch_home']
    home=(root/relative).resolve()
    config_dir = home / 'config'
    if not (any((config_dir / name).is_file() for name in (CONFIG_NAME, LEGACY_CONFIG_NAME))
            or (home / 'defaults' / 'frb_launch_data.template.json').is_file()):
        raise RuntimeError('Launch設定が見つかりません: '+str(config_dir / CONFIG_NAME))
    return home


def bundled_studio_root(launch_home_dir):
    """Find Studio by installation layout, independently of old JSON paths.

    Supported layouts (prefer an existing EXE, then a source-only tree):
      1. FRB_Launch/Studio              (portable bundle)
      2. FRB_Apps/FRB_Studio           (independent sibling app)

    A Studio source tree also counts as an installation root.  In that case,
    the menu can report the precise missing _publish EXE and its build step,
    instead of incorrectly trying the old F:/FRB/tools/... setting.

    None means no recognizable local Studio: retain the configured fallback.
    The process working directory is never used.
    """
    home = Path(launch_home_dir).resolve()
    candidates = (home / 'Studio', home.parent / 'FRB_Studio')
    # Prefer a runnable Studio over an incomplete source-only Studio.
    for candidate in candidates:
        exe = candidate / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
        if exe.is_file():
            return str(candidate.resolve())
    for candidate in candidates:
        project = candidate / 'NativeShell' / 'FRBStudio.NativeShell.csproj'
        if project.is_file():
            return str(candidate.resolve())
    return None


# One resolver for all Launch -> Studio CLI bridges. A linked PyInstaller
# development build has launch_home.json; a shipped executable does not.
import logging
import os
import shutil
import sys

_CLI_LOG = logging.getLogger('frb.launch.diagnostics')


def portable_runtime(home):
    home = Path(home).resolve()
    return ((home / 'installed_release.json').is_file() or
            (getattr(sys, 'frozen', False) and
             Path(sys.executable).resolve().parent == home and
             not (home / 'launch_home.json').is_file()))


def resolve_studio_cli(home, cli, configured=None):
    home = Path(home).resolve()
    strict = portable_runtime(home)
    candidates = [home / 'Studio']
    if not strict:
        candidates += [home.parent / 'FRB_Studio', configured,
                       home.parent / 'FRBStudio_App', home.parent / 'Studio',
                       home.parent.parent / 'FRBStudio_App', home]
    for candidate in candidates:
        if not candidate:
            continue
        root = Path(candidate).resolve()
        target = root / 'tools' / cli / 'cli.mjs'
        _CLI_LOG.info('Studio CLI candidate: %s exists=%s portable=%s', target, target.is_file(), strict)
        if target.is_file():
            _CLI_LOG.info('Studio CLI selected: %s', target)
            return root
    _CLI_LOG.warning('Studio CLI missing: home=%s cli=%s portable=%s', home, cli, strict)
    return None


def resolve_node(home, studio_root=None):
    home = Path(home).resolve()
    strict = portable_runtime(home)
    studio = (home / 'Studio') if strict else (Path(studio_root).resolve() if studio_root else home / 'Studio')
    candidates = [home / 'runtime/node/node.exe', studio / 'runtime/node/node.exe']
    if not strict:
        candidates += [home / 'runtime/node.exe', studio / 'tools/change_core/runtime/node.exe',
                       os.environ.get('FRB_LAUNCH_NODE', '').strip(),
                       studio / 'portable/node.exe', studio / 'node.exe',
                       studio / 'tools/change_core/portable/node.exe']
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_file() and not strict and not path.is_absolute():
            found = shutil.which(str(candidate))
            if found:
                path = Path(found)
        _CLI_LOG.info('Node candidate: %s exists=%s portable=%s', path, path.is_file(), strict)
        if path.is_file():
            result = str(path.resolve())
            _CLI_LOG.info('Node selected: %s', result)
            return result
    if not strict:
        found = shutil.which('node') or shutil.which('node.exe')
        if found:
            result = str(Path(found).resolve())
            _CLI_LOG.info('Node selected (PATH): %s', result)
            return result
    _CLI_LOG.warning('Node missing: home=%s studio=%s portable=%s', home, studio, strict)
    return None
