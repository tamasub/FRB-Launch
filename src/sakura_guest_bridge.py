"""Opt-in Sakura top-level third-column guest; preserve existing windows."""
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
