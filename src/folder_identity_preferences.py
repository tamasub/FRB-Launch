"""Filesystem identity for Launch UI preferences, not Launch DataJSON.

On a filesystem that exposes stable inode/file indices, (st_dev, st_ino)
identifies the currently visited folder across a rename or same-volume move.
Only the ONE opened directory is stat'ed.  An unavailable/zero identity falls
back to a normalized path, so network and unusual filesystems still work.
This is a preference lookup, not a file relocation tracker.
"""

import hashlib
import ntpath
import os
import stat


def normalized_folder_path(path):
    if not path:
        return None
    normalized = ntpath.normcase(ntpath.normpath(str(path).replace('/', '\\')))
    return normalized if normalized and normalized != '.' else None


def path_fallback_token(path):
    normalized = normalized_folder_path(path)
    if normalized is None:
        return None
    return 'path-' + hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def folder_identity_token(path):
    """Return a QSettings-safe opaque token, id-first with a path fallback.

    Python 3.5+ supplies the Windows file index as st_ino where available.
    Do not accept a non-directory, missing file or zero file index as an ID.
    """
    fallback = path_fallback_token(path)
    if fallback is None:
        return None
    try:
        meta = os.stat(path)
        if stat.S_ISDIR(meta.st_mode) and int(meta.st_ino) > 0:
            # Include device/volume: file indices are not globally unique.
            return 'id-{:x}-{:x}'.format(int(meta.st_dev), int(meta.st_ino))
    except (OSError, ValueError, TypeError, OverflowError):
        pass
    return fallback
