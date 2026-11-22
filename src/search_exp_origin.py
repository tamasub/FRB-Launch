"""Read-only origin resolution for search results opened through Files Exp/EX.

A search Location has no parent. When its file/folder is opened, its REAL
logical ancestry comes from the already configured Exp roots (JSON mount or
physical shortcut). Never manufacture a direct root or expand/select Exp here.
"""

import ntpath
from directory_entry_origin import within_entry


def _path_length(path):
    return len(ntpath.normcase(ntpath.normpath(str(path or ''))))


def search_exp_origin(directory, roots, expand):
    """Return go_to_directory options for the best existing Exp ancestry.

    ``roots`` is an ordered snapshot of (label, root-info) pairs. Descendant
    virtual JSON definitions may be examined from their stored children but
    unloaded Qt/physical folder rows are NEVER expanded by this function.

    The longest containing logical mount wins. At equal depth an explicit JSON
    mount wins over a physical shortcut, and identical aliases retain their
    authored Exp order. When no known root applies, use the absolute physical
    path only, with no new Exp root.
    """
    if not directory:
        return {'absolute_location': True}
    candidates = []
    order = 0
    for title, info in roots:
        if not isinstance(info, dict):
            continue
        path = info.get('path')
        if (path and not info.get('pc') and not info.get('direct_root')
                and within_entry(directory, path)):
            identity = info.get('studio_identity') or {}
            options = {'registered_root': {
                'root_path': str(path), 'title': str(title or path),
                'root_id': str(identity.get('item_id') or path),
            }}
            candidates.append((_path_length(path), 0, -order, options))
            order += 1
        virtual = info.get('virtual')
        if not isinstance(virtual, dict):
            continue
        stack = [virtual]
        while stack:
            node = stack.pop()
            stack.extend(reversed(node.get('children') or ()))
            if node.get('source') != 'launch_json' or node.get('kind') != 'linked_directory':
                continue
            raw = (node.get('row') or {}).get('launch_browse_target')
            if not raw:
                continue
            try:
                mount = str(expand(raw) or '')
            except (OSError, ValueError, TypeError):
                continue
            if mount and within_entry(directory, mount):
                options = {'mount_origin': {'node': node, 'entry_path': mount}}
                candidates.append((_path_length(mount), 1, -order, options))
                order += 1
    if not candidates:
        return {'absolute_location': True}
    return max(candidates, key=lambda record: record[:3])[3]


def search_exp_origin_from_panel(directory, panel, expand, data_role):
    """Read Exp root DATA ONLY; do not modify its model, focus or selection."""
    if panel is None:
        return {'absolute_location': True}
    model = getattr(panel, 'model', None)
    if model is None:
        return {'absolute_location': True}
    parent = model.invisibleRootItem()
    roots = []
    for row in range(parent.rowCount()):
        item = parent.child(row)
        if item is None:
            continue
        info = item.data(data_role)
        if isinstance(info, dict) and not info.get('separator_before_pc'):
            roots.append((item.text(), info))
    return search_exp_origin(directory, roots, expand)
