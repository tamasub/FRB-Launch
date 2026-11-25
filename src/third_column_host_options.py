"""Per-user third-column native host switches.

The three public options use explicit UserConfig JSON values when present;
legacy INI flags remain the fallback before migration. Studio always uses its private INI flag.
"""
from __future__ import annotations

import configparser
import os
import json
from pathlib import Path

_OPTION_NAMES = frozenset(('studio', 'sakura', 'obsidian', 'vscode'))
_TRUE = frozenset(('true', '1', 'yes', 'on'))
PUBLIC_APPS = ('obsidian', 'vscode', 'sakura')
OPTION_FILE = 'app_embedding_options.json'
_TRIAL_FLAGS = {'obsidian': 'FRB_OBSIDIAN_IME_OVERLAY',
                'vscode': 'FRB_VSCODE_GUEST_OVERLAY',
                'sakura': 'FRB_SAKURA_GUEST_OVERLAY'}
_runtime_state = None
_runtime_values = None


def _ini_value(state, app):
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with (Path(state) / 'state.ini').open('r', encoding='utf-8-sig') as source:
            parser.read_file(source)
        value = parser.get('General', 'embed_' + app, fallback='').strip().lower()
        if value in _TRUE:
            return True
        if value in {'false', '0', 'no', 'off'}:
            return False
    except (OSError, UnicodeError, configparser.Error, ValueError):
        pass
    return None


def ensure_app_embedding_user_options(state, *, environment=None):
    """Initialize the Generic Editor with the actual legacy user choices, once.

    Never rewrite state.ini or an existing UserConfig file. This is a migration
    of three scalar preferences, not a second general-purpose JSON composer.
    """
    env = os.environ if environment is None else environment
    state = Path(state)
    path = state / 'UserConfig' / OPTION_FILE
    if path.exists():
        if not path.is_file():
            raise RuntimeError('アプリ連携設定の保存先がファイルではありません: ' + str(path))
        return path
    values = {}
    for app in PUBLIC_APPS:
        value = _ini_value(state, app)
        # VSCode/Sakura use trial flags when INI is absent. Obsidian's routing
        # requires explicit opt-in, so keep its legacy absent value OFF.
        if value is None:
            value = app != 'obsidian' and env.get(_TRIAL_FLAGS[app], '').strip() == '1'
        values['embed_' + app] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as output:
            output.write(json.dumps(values, ensure_ascii=False, indent=2) + '\n')
    except FileExistsError:
        pass
    return path


def _read_configured_embedded_editor(launch_home, app, env):
    """Read explicit public JSON override, then the legacy INI preference.

    Invalid explicit JSON fails closed; it must never invite a native window.
    No User JSON preserves the pre-existing legacy behavior.
    """
    if app not in _OPTION_NAMES:
        return None
    user_root = Path(env.get('LOCALAPPDATA') or Path.home()) / 'FRBLaunch'
    if app in PUBLIC_APPS:
        path = user_root / 'UserConfig' / OPTION_FILE
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict):
                return False
            key = 'embed_' + app
            if key in data:
                return data[key] is True
            # The Generic Editor may store only values different from System.
            # Once a User JSON exists, absent keys inherit System, not stale INI.
            home = Path(launch_home or env.get('FRB_LAUNCH_HOME') or Path(__file__).resolve().parents[1])
            try:
                system = json.loads((home / 'config' / OPTION_FILE).read_text(encoding='utf-8-sig'))
            except (OSError, UnicodeError, ValueError):
                return False
            return isinstance(system, dict) and system.get(key) is True
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError, ValueError):
            return False
    return _ini_value(user_root, app)


def initialize_app_embedding_runtime(launch_home, *, environment=None):
    """Freeze the three guest settings for this process until restart.

    Saving while a guest is attached/pending must not change its polling or
    handoff protocol halfway through. The hidden Studio flag is not migrated.
    """
    global _runtime_state, _runtime_values
    env = os.environ if environment is None else environment
    state = Path(env.get('LOCALAPPDATA') or Path.home()) / 'FRBLaunch'
    _runtime_values = {app: _read_configured_embedded_editor(launch_home, app, env)
                       for app in PUBLIC_APPS}
    _runtime_state = state


def configured_embedded_editor(launch_home, app, *, environment=None):
    env = os.environ if environment is None else environment
    state = Path(env.get('LOCALAPPDATA') or Path.home()) / 'FRBLaunch'
    if _runtime_values is not None and state == _runtime_state and app in PUBLIC_APPS:
        return _runtime_values[app]
    return _read_configured_embedded_editor(launch_home, app, env)


def embedded_editor_enabled(launch_home, app):
    """Read the explicit guest switch; missing/invalid is OFF."""
    return configured_embedded_editor(launch_home, app) is True
