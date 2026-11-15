"""Seed user-owned FRB Launch state.ini once from a system-managed template.

Only settings exposed in the gear menu are seeded.  Everything else (window
geometry, history, session state, etc.) remains user/runtime-owned.  If the
sample omits a key, app.py / pointer_warp_policy.py keep their existing
QSettings fallback values; do NOT duplicate those defaults here.
"""
from __future__ import annotations

import configparser
import logging
from pathlib import Path


# QSettings stores these top-level keys in the [General] INI section.
SEED_KEYS = (
    'appearance_theme',
    'vdi_no_cursor_warp',
    'dismiss_on_outside_click',
    'folder_open_mode',
    'desktop_remote_enabled',
    'hide_page_buttons',
    'experiment_remote_15_column',
    'experiment_mouse_pointer_rod',
    'experiment_mouse_pointer_rod_windows',
    'experiment_mouse_pointer_rod_smart',
)
_BOOLEAN_KEYS = set(SEED_KEYS) - {'appearance_theme', 'folder_open_mode'}
_TRUE = {'1', 'true', 'yes', 'on'}
_FALSE = {'0', 'false', 'no', 'off'}


def _normalized_value(key: str, value: str) -> str | None:
    normalized = value.strip().lower()
    if key in _BOOLEAN_KEYS:
        if normalized in _TRUE:
            return 'true'
        if normalized in _FALSE:
            return 'false'
    elif key == 'appearance_theme' and normalized in {'light', 'dark'}:
        return normalized
    elif key == 'folder_open_mode' and normalized in {'single', 'double'}:
        return normalized
    return None


def _template_values(template: Path) -> dict[str, str]:
    if not template.is_file():
        return {}
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # Do not unexpectedly rewrite user-authored names.
    try:
        with template.open('r', encoding='utf-8-sig') as source:
            parser.read_file(source)
    except (OSError, UnicodeError, configparser.Error) as exc:
        logging.warning('FRB Launch default state.ini ignored: %s: %s', template, exc)
        return {}
    if not parser.has_section('General'):
        logging.warning('FRB Launch default state.ini needs a [General] section: %s', template)
        return {}

    results = {}
    for key in SEED_KEYS:
        if not parser.has_option('General', key):
            continue
        raw = parser.get('General', key)
        value = _normalized_value(key, raw)
        if value is None:
            logging.warning('FRB Launch default state.ini invalid value ignored: %s=%r', key, raw)
        else:
            results[key] = value
    return results


def ensure_initial_state_ini(template: Path, destination: Path) -> Path:
    """Create a minimal QSettings-compatible INI exactly once.

    Existing state.ini is *never* read/rewritten/repaired from defaults.  An
    absent template or an absent/invalid individual key deliberately leaves
    that value to the application's existing built-in default.
    """
    destination = Path(destination)
    if destination.exists():
        if not destination.is_file():
            raise RuntimeError('Launch状態の保存先がファイルではありません: ' + str(destination))
        return destination

    entries = _template_values(Path(template))
    lines = ['[General]'] + [f'{key}={entries[key]}' for key in SEED_KEYS if key in entries]
    contents = '\n'.join(lines) + '\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open('x', encoding='utf-8', newline='\n') as out:
            out.write(contents)
    except FileExistsError:
        # Another Launch process won the initial create. Its file is canonical.
        pass
    return destination
