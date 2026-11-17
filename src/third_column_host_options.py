"""Hidden experimental third-column native host switches in state.ini.

The user-owned state file is shared with the rest of Launch's INI options.
An absent, invalid or non-boolean setting always means disabled. Whether
an option appears in the options UI is a separate ViewDef concern.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

_OPTION_NAMES = frozenset(('studio', 'sakura', 'obsidian'))
_TRUE = frozenset(('true', '1', 'yes', 'on'))


def embedded_editor_enabled(launch_home, app):
    """Read [General] embed_<app> from the user's state.ini (not Launch home).

    ``launch_home`` is retained for compatibility with existing call sites.
    Missing/invalid settings deliberately fail closed, especially on upgrades
    of existing user state.ini files where newly introduced keys are absent.
    """
    if app not in _OPTION_NAMES:
        return False
    user_root = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FRBLaunch'
    settings_file = user_root / 'state.ini'
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with settings_file.open('r', encoding='utf-8-sig') as source:
            parser.read_file(source)
        if not parser.has_section('General'):
            return False
        return parser.get('General', 'embed_' + app, fallback='').strip().lower() in _TRUE
    except (OSError, UnicodeError, configparser.Error, ValueError):
        return False
