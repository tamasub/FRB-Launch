"""Pure helpers for Launch's opt-in-by-registration Shell Link records.

The tracking data is attached only to newly registered *local files*. Legacy
JSON rows never change. A missing original target must not silently fall back
to an unrelated file, and a resolved path is never executed as a shell command.
"""
from __future__ import annotations

import os
from pathlib import Path
from shell_link_stream import ShellLinkError, resolve_link_data


def tracking_target_update(row, *, resolver=resolve_link_data):
    """Return (path, refreshed_link_data) if a missing file can be tracked.

    Return None for untracked/existing files, directory actions, or complex
    multi-step authored entries. Raise ShellLinkError for a broken tracked link.
    """
    blob = row.get('launch_shell_link_data') or ''
    actions = row.get('launch_actions') or []
    if (not blob or not isinstance(actions, list) or len(actions) != 1 or
            actions[0].get('launch_action_type') != 'Open' or
            actions[0].get('launch_browser') or
            actions[0].get('launch_browser_profile')):
        return None
    original = actions[0].get('launch_target')
    if not isinstance(original, str) or not os.path.isabs(original):
        return None
    if os.path.isfile(original):
        return None
    path, refreshed_data = resolver(blob)
    if not os.path.isfile(path):
        raise ShellLinkError('追跡先ファイルが存在しません')
    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(original)):
        return None
    return path, refreshed_data


def update_record_changes(row, new_path, new_blob):
    """Preserve authored label/description unless still matching the old path."""
    actions = row['launch_actions']
    old_path = actions[0]['launch_target']
    updated = [dict(action) for action in actions]
    updated[0]['launch_target'] = new_path
    changes = [
        {'path': 'launch_actions', 'value': updated},
        {'path': 'launch_shell_link_data', 'value': new_blob},
    ]
    if row.get('description') == old_path:
        changes.append({'path': 'description', 'value': new_path})
    if row.get('title') == Path(old_path).name:
        changes.append({'path': 'title', 'value': Path(new_path).name})
    return changes


def matches_original_tracking(authoritative, cached):
    """Refuse to overwrite a concurrent Studio edit or repointed shortcut."""
    fresh = authoritative.get('launch_actions') or []
    original = cached.get('launch_actions') or []
    return (authoritative.get('launch_shell_link_data') and
            authoritative.get('launch_shell_link_data') == cached.get('launch_shell_link_data') and
            len(fresh) == len(original) == 1 and
            fresh[0].get('launch_target') == original[0].get('launch_target') and
            fresh[0].get('launch_action_type') == original[0].get('launch_action_type') == 'Open')
