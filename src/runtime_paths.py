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
    if not any((config_dir / name).is_file() for name in (CONFIG_NAME, LEGACY_CONFIG_NAME)):
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
