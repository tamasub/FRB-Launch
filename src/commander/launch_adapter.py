"""Minimal FRB Launch dependency: use its authored Files roots for picker start."""
from pathlib import Path


def launch_workspace_root(launcher, script):
    """Prefer the broadest registered Files root containing the script.

    Never guess a global drive root. If there is no matching registration,
    use the script's folder as an explicit, predictable fallback.
    """
    target = Path(script).resolve()
    try:
        from remote_files_exp_roots import registered_folder_roots
        roots = registered_folder_roots(launcher._remote_files_first_column_rows(),
                                        launcher.expander().expand)
        candidates = []
        for entry in roots:
            raw = entry.get('path')
            if not raw:
                continue
            folder = Path(raw).resolve()
            if folder.is_dir() and (folder == target.parent or folder in target.parents):
                candidates.append(folder)
        if candidates:
            return min(candidates, key=lambda item: len(item.parts))
    except (OSError, ValueError, RuntimeError, AttributeError, KeyError):
        pass
    return target.parent


def guarded_open(launcher, script, workspace_root):
    """Late QTimer callback: report failures instead of leaking Qt tracebacks."""
    from commander.window import launch_commander
    try:
        launch_commander(launcher, script, workspace_root=workspace_root)
    except (OSError, ValueError, RuntimeError) as exc:
        launcher.error('FRB Commanderを起動できません: ' + str(exc))
