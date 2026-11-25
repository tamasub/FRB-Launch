"""リモコン表示モード（Qt非依存）。廃止済み1.5列は復元しない。"""

MODES = ('off', 'window', 'wheel')


def _enabled(value):
    return str(value).strip().lower() in ('true', '1', 'yes', 'on')


def normalize_remote_display_mode(value, *, legacy_enabled=False, legacy_column15=False):
    """有効な現行値を優先。廃止値はoff。旧別Windowのみ互換維持。"""
    if value is not None:
        normalized = str(value).strip().lower()
        if normalized in MODES:
            return normalized
        # Never fall through to the old desktop flag for a retired mode.
        return 'off'
    if _enabled(legacy_column15):
        return 'off'
    if _enabled(legacy_enabled):
        return 'window'
    return 'off'


def mode_is_remote_window(mode):
    return mode == 'window'
