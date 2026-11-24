"""Choose Windows Shell icons for filesystem and Launch-JSON file entries.

File rows dropped into the Launch settings JSON store their original path in
``launch_actions[].launch_target``. The Files List virtual projection deliberately
removes ``_file`` (it must never treat an authored shortcut as a physical file),
so icon presentation must resolve the file *type* without adding a filesystem
identity back to that projection.

For ordinary files, query QFileIconProvider using a synthetic file name. This
avoids reading Box/OneDrive/SharePoint placeholder contents or stat-ing paths.
Executable/shortcut/ICO files keep their individual path icons.
"""
from pathlib import PureWindowsPath


PATH_ICON_EXTENSIONS = frozenset({'.exe', '.lnk', '.ico', '.url', '.appref-ms'})


def _open_action_file(row):
    """File target of an authored 'file' shortcut, for icon lookup only.

    Do not infer icons from arbitrary commands or open URLs, and do not expand
    variables (which belong to the execution path). The saved JSON is untouched.
    """
    if row.get('icon_key') != 'file' or row.get('item_kind') in ('directory', 'category'):
        return ''
    actions = row.get('launch_actions')
    if not isinstance(actions, list):
        return ''
    for action in actions:
        if not isinstance(action, dict) or action.get('launch_action_type') != 'Open':
            continue
        target = action.get('launch_target')
        if not isinstance(target, str) or not target.strip():
            continue
        target = target.strip()
        # Files registered by drag/drop are absolute Windows drive/UNC paths.
        # Do not mistake URL path suffixes for local file extensions.
        if '://' in target or target.lower().startswith(('shell:', 'ms-settings:')):
            continue
        if not (len(target) >= 3 and target[1] == ':' and target[2] in ('\\', '/')
                or target.startswith('\\\\')):
            continue
        if PureWindowsPath(target).suffix:
            return target
    return ''


def icon_source_path(row):
    """Original path for display-only icon resolution, including JSON Open rows.

    This never creates an ``_file`` identity in a virtual Launch row.
    """
    return (row.get('_icon_file') or row.get('_file') or row.get('_browse_file')
            or row.get('_indexed_file') or _open_action_file(row))


def icon_lookup(row):
    """Return ('type', extension), ('path', path), or ('default', key).

    The result changes presentation only; no file open, path mutation or JSON
    change is allowed. Folder and manually authored icon keys remain unchanged.
    """
    path = icon_source_path(row)
    if not path:
        return ('default', row.get('icon_key', 'command'))

    # Installed applications and drives need their real Windows Shell icon.
    if row.get('_icon_file') or row.get('_system_drive'):
        return ('path', path)

    if row.get('icon_key') == 'file' and row.get('item_kind') not in ('directory', 'category'):
        extension = PureWindowsPath(str(path)).suffix.casefold()
        if extension and extension not in PATH_ICON_EXTENSIONS:
            return ('type', extension)

    return ('path', path)
