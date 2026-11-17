"""Resolve genuine Files List .md / Studio-managed .json leaves for an opt-in pane.

Only the physical file path (not an authored Launch command) is eligible.
Enter and regular Launch actions continue through their existing routes.
"""
from pathlib import Path
from file_index import studio_managed_json


def studio_preview_target(row, studio_root):
    """Return (file_path, studio_exe, studio_root) or None, without side effects."""
    if not isinstance(row, dict) or row.get('_launch_virtual_node') is not None:
        return None
    raw = row.get('_browse_file') or row.get('_indexed_file') or row.get('_file')
    if not isinstance(raw, str) or not raw.strip() or not studio_root:
        return None
    try:
        path = Path(raw).resolve(strict=True)
        root = Path(studio_root).resolve(strict=True)
        exe = root / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
        if not path.is_file() or not exe.is_file():
            return None
        suffix = path.suffix.casefold()
        if suffix != '.md' and not (suffix == '.json' and studio_managed_json(path, root)):
            return None
        return str(path), str(exe), str(root)
    except (OSError, ValueError, RuntimeError):
        return None


def studio_start_command(target):
    """Reuse NativeShell's existing startup bridge and its real Save commands."""
    path, exe, root = target[:3]
    extra_arguments = tuple(target[3]) if len(target) > 3 else ()
    flag = '--open-md=' if Path(path).suffix.casefold() == '.md' else '--open-json='
    return [exe, flag + path, *extra_arguments], root
