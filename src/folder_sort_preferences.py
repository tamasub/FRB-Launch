"""Per-physical-folder Files List sort settings, outside Launch DataJSON.

Nondefault sorts use the folder's filesystem identity instead of its path.
Old path-keyed v1 preferences are migrated lazily on directory visit; the
existing global sort remains intentionally ignored.
"""
import hashlib

from folder_identity_preferences import (folder_identity_token,
                                         normalized_folder_path)

DEFAULT_SORT = 'name'
PREFIX = 'expanded_middle_sort_by_folder_v2/'
LEGACY_PREFIX = 'expanded_middle_sort_by_folder_v1/'


def legacy_directory_sort_key(directory):
    path = normalized_folder_path(directory)
    if path is None:
        return None
    return LEGACY_PREFIX + hashlib.sha256(path.encode('utf-8')).hexdigest()


def directory_sort_key(directory):
    token = folder_identity_token(directory)
    return PREFIX + token if token else None


def _sync(settings):
    sync = getattr(settings, 'sync', None)
    if callable(sync):
        sync()


def load_directory_sort(settings, directory, valid_modes):
    key = directory_sort_key(directory)
    if key is None:
        return DEFAULT_SORT
    # If this physical folder has already been customized, never fall back
    # to the obsolete path preference for a *different* folder at that path.
    value = settings.value(key, None)
    if value is not None:
        return str(value) if str(value) in valid_modes else DEFAULT_SORT
    legacy = legacy_directory_sort_key(directory)
    legacy_mode = settings.value(legacy, None) if legacy else None
    if legacy_mode is None:
        return DEFAULT_SORT
    mode = (str(legacy_mode) if str(legacy_mode) in valid_modes
            else DEFAULT_SORT)
    # A path-only key is a fallback when no filesystem ID is available;
    # remove the superseded v1 setting once the directory is visited.
    if mode != DEFAULT_SORT:
        settings.setValue(key, mode)
    if legacy != key:
        settings.remove(legacy)
    _sync(settings)
    return mode


def save_directory_sort(settings, directory, mode, valid_modes):
    """Write only overrides; remove a legacy path key on the first edit."""
    if mode not in valid_modes:
        raise ValueError('Unsupported folder sort: ' + str(mode))
    key = directory_sort_key(directory)
    if key is None:
        return False
    if mode == DEFAULT_SORT:
        settings.remove(key)
    else:
        settings.setValue(key, mode)
    legacy = legacy_directory_sort_key(directory)
    if legacy and legacy != key:
        settings.remove(legacy)
    _sync(settings)
    return True


def transfer_directory_sort(settings, old_directory, new_directory, valid_modes):
    """Preserve legacy preferences during a Launch-controlled rename.

    ID-keyed preferences need no transfer: the destination is the same folder.
    When old path no longer exists, the old legacy path key is still movable.
    """
    old_key = directory_sort_key(old_directory)
    new_key = directory_sort_key(new_directory)
    if not old_key or not new_key:
        return False
    old_legacy = legacy_directory_sort_key(old_directory)
    new_legacy = legacy_directory_sort_key(new_directory)
    if old_key == new_key:
        return False
    mode = settings.value(old_key, None)
    if mode is None and old_legacy:
        mode = settings.value(old_legacy, None)
    if mode is not None and str(mode) in valid_modes:
        save_directory_sort(settings, new_directory, str(mode), valid_modes)
    if old_key != new_key:
        settings.remove(old_key)
    if old_legacy not in (None, new_key, new_legacy):
        settings.remove(old_legacy)
    _sync(settings)
    return True
