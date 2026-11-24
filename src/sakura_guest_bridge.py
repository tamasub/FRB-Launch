"""Sakura top-level third-column guest; preserve existing native windows."""
import os
from pathlib import Path


def enabled(environment=None):
    """Use state.ini first; honor old trial env only when not configured."""
    env = os.environ if environment is None else environment
    from third_column_host_options import configured_embedded_editor
    configured = configured_embedded_editor(None, 'sakura', environment=env)
    if configured is not None:
        return configured
    return env.get('FRB_SAKURA_GUEST_OVERLAY', '').strip() == '1'


def caption_matches_file(title, path):
    # Sakura captions normally contain the leaf name, but not always the full path.
    return bool(title and Path(path).name.casefold() in title.casefold())


def new_hwnd_for_file(windows, baseline, path):
    # Require a newly created top-level HWND; never borrow a desktop window.
    found = [(int(hwnd), int(pid)) for hwnd, pid, title in windows
             if int(hwnd) not in baseline and int(pid) > 0
             and caption_matches_file(title, path)]
    return found[0][0] if len(found) == 1 else None


def active_group_trial_enabled(environment=None):
    """Default-on Sakura group hint; explicit 0 disables it for rollback.

    The historical *_TRIAL variable name is retained for compatibility.
    This never targets a specific native HWND: safe() must still approve it.
    """
    env = os.environ if environment is None else environment
    value = env.get('FRB_SAKURA_ACTIVE_GROUP_TRIAL', '').strip().lower()
    return value not in ('0', 'false', 'off', 'no')


def active_group_trial_safe(attached_hwnd, visible_windows, parked, auto_ejected=()):
    """Conservative gate: no foreign/explicitly detached visible Sakura.

    Sakura's GROUP=0 refers to its *globally* active group. If another user
    window is visible, we cannot prove which group would receive the file.
    This narrows the risk for the default-on hint; a caller can explicitly
    disable it with FRB_SAKURA_ACTIVE_GROUP_TRIAL=0.
    """
    attached_hwnd = int(attached_hwnd or 0)
    if not attached_hwnd:
        return False
    ejected = set(auto_ejected)
    if any(key[0] == 'sakura' for key in ejected):
        return False
    managed = {attached_hwnd}
    managed.update(int(hwnd) for key, hwnd in parked.items()
                   if key[0] == 'sakura' and key not in ejected)
    visible = {int(hwnd) for hwnd, _pid, _title in visible_windows}
    return attached_hwnd in visible and visible.issubset(managed)
