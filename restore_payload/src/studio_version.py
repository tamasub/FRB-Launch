"""Read the installed FRB Studio version from its own editable metadata file.

This is display metadata, not a substitute for the signed release manifest.
No executable is launched and no user-controlled Launch data is modified.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STUDIO_VERSION_RELATIVE = Path('defs') / 'app_version.json'
_VERSION_PATTERN = re.compile(r'\d+\.\d+\.\d+\Z')


def read_studio_version(launch_home, install_root=None, studio_root=None):
    """Return the first valid Studio version from a known installation layout.

    Prefer the explicitly configured Studio used by Launch. A portable
    installation and the independent sibling application are also supported.
    A corrupt/missing file is ignored and the caller may use manifest fallback.
    """
    launch_home = Path(launch_home).resolve()
    roots = (
        studio_root,
        Path(install_root) / 'Studio' if install_root else None,
        launch_home / 'Studio',
        launch_home.parent / 'FRB_Studio',
    )
    seen = set()
    for root in roots:
        if not root:
            continue
        try:
            directory = Path(root).resolve()
            if directory in seen:
                continue
            seen.add(directory)
            metadata = directory / STUDIO_VERSION_RELATIVE
            obj = json.loads(metadata.read_text(encoding='utf-8-sig'))
            if not isinstance(obj, dict) or obj.get('app_name') != 'FRB Studio':
                continue
            version = obj.get('app_version')
            if isinstance(version, str) and _VERSION_PATTERN.fullmatch(version):
                return version
        except (OSError, ValueError, TypeError):
            continue
    return None
