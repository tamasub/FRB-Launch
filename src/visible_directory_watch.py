"""Small, Qt-free directory-watch selection for FRB Files navigation.

Watch parents of *displayed* names: a rename changes the parent directory.
Do not walk the filesystem recursively or watch hidden Exp subtrees.
"""

import os


def normalized_watch_path(path):
    if not path:
        return ''
    try:
        return os.path.normcase(os.path.abspath(os.fspath(path)))
    except (OSError, TypeError, ValueError):
        return ''


def physical_crumb_paths(segments):
    """Physical targets may be ordinary paths or logical ('physical', path)."""
    for _label, target in segments or ():
        if isinstance(target, tuple) and len(target) >= 2:
            if target[0] != 'physical':
                continue
            target = target[1]
        elif not isinstance(target, str):
            continue
        path = normalized_watch_path(target)
        if path:
            yield path


def breadcrumb_parent_watches(segments, *, limit=32):
    """Parents of physical crumb labels; virtual JSON nodes are skipped."""
    result = []
    seen = set()
    for path in physical_crumb_paths(segments):
        parent = normalized_watch_path(os.path.dirname(path)) if path else ''
        if parent and parent != path and parent not in seen and os.path.isdir(parent):
            seen.add(parent)
            result.append(parent)
            if len(result) >= limit:
                break
    return result


def exp_visible_watches(rows, *, limit=48):
    """Given (folder_path, expanded, linked_path) for ON-SCREEN tree rows."""
    result = []
    seen = set()
    for path, expanded, linked_path in rows:
        real = normalized_watch_path(path)
        linked = normalized_watch_path(linked_path)
        candidates = []
        if real:
            parent = normalized_watch_path(os.path.dirname(real))
            if parent != real:
                candidates.append(parent)  # Rename of the visible row.
            if expanded:
                candidates.append(real)  # Addition/removal of visible children.
        elif linked and expanded:
            candidates.append(linked)  # Virtual mount exposes physical children.
        for candidate in candidates:
            if (candidate and candidate not in seen and
                    os.path.isdir(candidate)):
                seen.add(candidate)
                result.append(candidate)
                if len(result) >= limit:
                    return result
    return result


def stat_directory_identity(path):
    """(device, filesystem-file-id) for safe same-parent rename detection."""
    try:
        stat = os.stat(path, follow_symlinks=False)
        inode = int(stat.st_ino)
        if inode and os.path.isdir(path):
            return (stat.st_dev, inode)
    except (OSError, ValueError, TypeError):
        pass
    return None


def relocated_crumb_directory(current, segments, identities, *, scan_limit=4096):
    """Find a renamed visible ancestor by filesystem ID, without guessing.

    Only a same-parent rename is followed. Moves across parents/drives or
    ambiguous/unidentifiable paths are deliberately ignored. Never poll.
    """
    current = normalized_watch_path(current)
    if not current or os.path.isdir(current):
        return None
    for old in physical_crumb_paths(segments):
        if os.path.isdir(old):
            continue
        identity = identities.get(old)
        parent = os.path.dirname(old)
        if not identity or not os.path.isdir(parent):
            continue
        try:
            relative = os.path.relpath(current, old)
        except ValueError:
            continue
        if relative == os.pardir or relative.startswith(os.pardir + os.sep):
            continue
        found = None
        try:
            with os.scandir(parent) as entries:
                for index, entry in enumerate(entries):
                    if index >= scan_limit:
                        return None
                    if (entry.is_dir(follow_symlinks=False) and
                            stat_directory_identity(entry.path) == identity):
                        if found is not None:
                            return None  # Never guess between aliases.
                        found = entry.path
        except OSError:
            continue
        if found:
            rebased = os.path.normpath(os.path.join(found, relative))
            if os.path.isdir(rebased):
                return (old, rebased)
    return None
