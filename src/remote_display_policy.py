"""リモコン表示モードと旧設定からの移行規則（Qt非依存）。"""

MODES = ('off', 'column15', 'window', 'wheel')


def _enabled(value):
    return str(value).strip().lower() in ('true', '1', 'yes', 'on')


def normalize_remote_display_mode(value, *, legacy_enabled=False, legacy_column15=False):
    """新設定優先。古いstate.iniは従来の表示に読み替える。"""
    if value is not None and str(value).strip().lower() in MODES:
        return str(value).strip().lower()
    if _enabled(legacy_column15):
        return 'column15'
    if _enabled(legacy_enabled):
        return 'window'
    return 'off'


def mode_is_remote_window(mode):
    return mode in ('column15', 'window')
