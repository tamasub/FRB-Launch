"""Hidden experimental third-column native host switches in state.ini.

The user-owned state file is shared with the rest of Launch's INI options.
An absent, invalid or non-boolean setting always means disabled. Whether
an option appears in the options UI is a separate ViewDef concern.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

_OPTION_NAMES = frozenset(('studio', 'sakura', 'obsidian', 'vscode'))
_TRUE = frozenset(('true', '1', 'yes', 'on'))


def configured_embedded_editor(launch_home, app, *, environment=None):
    """Return True/False for an explicitly configured switch, None otherwise.

    Only the user's state.ini is authoritative. None permits the temporary
    2026-11-19 trial environment switches on older, unconfigured installs.
    """
    if app not in _OPTION_NAMES:
        return None
    env = os.environ if environment is None else environment
    user_root = Path(env.get('LOCALAPPDATA') or Path.home()) / 'FRBLaunch'
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with (user_root / 'state.ini').open('r', encoding='utf-8-sig') as source:
            parser.read_file(source)
        if not parser.has_section('General'):
            return None
        value = parser.get('General', 'embed_' + app, fallback='').strip().lower()
        if value in _TRUE:
            return True
        if value in {'false', '0', 'no', 'off'}:
            return False
    except (OSError, UnicodeError, configparser.Error, ValueError):
        pass
    return None


def embedded_editor_enabled(launch_home, app):
    """Read the explicit state.ini guest switch; missing/invalid is OFF."""
    return configured_embedded_editor(launch_home, app) is True
