"""Files List outbound drag policy. Only the user-owned state.ini controls it.

Missing or invalid values retain the adopted Explorer-compatible behavior.
Other drag sources stay on their original copy-only Qt path.
"""

_SETTING = 'files_list_explorer_drag'
_TRUE = {'1', 'true', 'yes', 'on'}
_FALSE = {'0', 'false', 'no', 'off'}


def files_list_shell_drag_enabled(settings):
    """Read QSettings value; return True unless explicitly switched off."""
    raw = settings.value(_SETTING, None)
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return True
    value = str(raw).strip().casefold()
    if value in _FALSE:
        return False
    if value in _TRUE:
        return True
    return True
