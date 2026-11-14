"""Choose the explicitly authored *development* Studio for Launch JSON editing.

The installed Studio bundled in a portable/update-test directory is the runtime
Studio and must not silently replace the author's development Studio root.
A portable user with no valid authored root continues to use bundled Studio.
"""
from __future__ import annotations

import os
from pathlib import Path


def editor_studio_root(data, runtime_studio_root):
    variables = data.get('launch_variables', ()) if isinstance(data, dict) else ()
    values = {row.get('variable_id'): row.get('launch_value')
              for row in variables if isinstance(row, dict)
              and row.get('enabled', True) and row.get('launch_variable_type') == 'literal'}
    # Source is explicit. Legacy studio_root is used only when there was no
    # source declaration, and never overrides a valid portable installation
    # with a stale missing path.
    candidates = [values.get('studio_source_root'), values.get('studio_root')]
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        candidate = os.path.expandvars(candidate.strip())
        path = Path(candidate)
        exe = path / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
        if path.is_dir() and exe.is_file():
            return str(path.resolve())
    return str(runtime_studio_root or '')
