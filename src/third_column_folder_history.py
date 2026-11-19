"""Launch-owned document origins for the third-column 'open containing folder' action.

Do not inspect editor HWND captions or alter Files List when opening a file.
Only paths explicitly opened through Launch are remembered, per editor type.
"""
import ntpath
import os


def _folder_key(path):
    # Windows paths must stay case-insensitive even in portable CI tests.
    return ntpath.normcase(ntpath.normpath(str(path)))


class ThirdColumnFolderHistory:
    def __init__(self):
        self._folders = {}
        self._active_owner = None

    def remember(self, owner, file_path):
        """Record a *successfully requested* physical editor file, newest first."""
        if owner not in ('studio', 'vscode', 'sakura', 'obsidian'):
            return False
        if not file_path or not isinstance(file_path, (str, os.PathLike)):
            return False
        path = str(file_path).strip()
        if not path:
            return False
        folder = ntpath.dirname(ntpath.normpath(path))
        if not folder or folder == path:
            return False
        folders = self._folders.setdefault(owner, [])
        key = _folder_key(folder)
        folders[:] = [item for item in folders if _folder_key(item) != key]
        folders.insert(0, folder)
        self._active_owner = owner
        return True

    def activate(self, owner):
        self._active_owner = owner if owner in self._folders else None

    def clear_active(self):
        self._active_owner = None

    def candidates(self):
        return tuple(self._folders.get(self._active_owner, ()))

    @property
    def owner(self):
        return self._active_owner
