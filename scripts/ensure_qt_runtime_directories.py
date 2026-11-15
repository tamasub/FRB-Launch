"""Keep PySide6's required DLL search directories across file-only release ZIPs.

PySide6's Windows startup checks for sibling ``shiboken6/libshiboken`` and
``PySide6/libpyside`` directories. A valid PyInstaller onedir build can contain
these as empty directories. Both the full update ZIP and portable ZIP are built
from file inventories, and therefore otherwise lose those empty directories.

Write a tiny SYSTEM-owned marker inside each directory. The normal manifest
and SHA-256 validation then preserve the directories in portable ZIPs and in
Updater installs, without touching any user settings or application sources.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = '.frb_qt_runtime_directory.txt'
REQUIRED_RELATIVE_DIRS = ('shiboken6/libshiboken', 'PySide6/libpyside')
MARKER_CONTENT = (
    'FRB Launch - PySide6 runtime directory marker.\n'
    'Required for Windows Qt DLL directory discovery. Do not delete.\n'
)


def qt_layouts(dist: Path):
    """Find PyInstaller layouts, supporting _internal and legacy flat onedir."""
    root = Path(dist)
    return tuple(base for base in (root / '_internal', root)
                 if (base / 'PySide6').is_dir())


def ensure_qt_runtime_directories(dist: Path, *, create: bool = False,
                                  require_qt: bool = True):
    """Validate native bindings and preserve folders (only if create=True).

    This is intentionally NOT a dependency installer: missing .pyd files fail
    closed, rather than being concealed by creating empty directories.
    """
    layouts = qt_layouts(Path(dist))
    if not layouts and require_qt:
        raise ValueError(
            'PySide6 runtime is missing from the Launch build. '
            'Run _build_windows.bat (PyInstaller onedir) before packaging.'
        )
    result = []
    for base in layouts:
        if not any((base / 'PySide6').glob('QtCore*.pyd')):
            raise ValueError('PySide6/QtCore*.pyd is missing: ' + str(base))
        shiboken = base / 'shiboken6'
        if not shiboken.is_dir() or not any(shiboken.glob('Shiboken*.pyd')):
            raise ValueError(
                'shiboken6/Shiboken*.pyd is missing: ' + str(shiboken) +
                '. Rebuild from a complete, matching PySide6/shiboken6 environment.'
            )
        for rel in REQUIRED_RELATIVE_DIRS:
            folder = base / rel
            marker = folder / MARKER
            if create:
                folder.mkdir(parents=True, exist_ok=True)
                marker.write_text(MARKER_CONTENT, encoding='utf-8')
            elif not marker.is_file():
                raise ValueError(
                    'PySide6 required folder is not protected for release: ' +
                    str(folder) + '. Run _build_windows.bat before packaging.'
                )
            result.append(marker)
    return tuple(result)


def main():
    parser = argparse.ArgumentParser(description='Preserve Qt Windows runtime directories in release archives.')
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Check only, no writes')
    args = parser.parse_args()
    try:
        markers = ensure_qt_runtime_directories(args.dist, create=not args.check)
    except (OSError, ValueError) as exc:
        parser.exit(1, '[ERROR] PySide6 runtime: ' + str(exc) + '\n')
    print('[OK] PySide6 runtime directories protected:', len(markers))
    for path in markers:
        print('  ', path)


if __name__ == '__main__':
    main()
