"""Fail closed if the onefile Updater accidentally includes a Tk runtime hook.

The GUI is implemented using Win32 ctypes, so tkinter/Tcl is not required.
Run immediately after PyInstaller, before distributing the EXE.
"""
from __future__ import annotations
import argparse
from pathlib import Path

FORBIDDEN = ('pyi_rth__tkinter', 'tkinter', '_tkinter')


def validate_toc(names):
    bad = [name for name in names if any(word in name.lower() for word in FORBIDDEN)]
    if bad:
        raise ValueError('Tkinter runtime unexpectedly included: ' + ', '.join(bad))


def verify(path: Path):
    if not path.is_file():
        raise FileNotFoundError(str(path))
    from PyInstaller.archive.readers import CArchiveReader
    reader = CArchiveReader(str(path))
    validate_toc(reader.toc.keys())
    # The bundled PYZ holds importable Python modules; inspect it too.
    for name, (*_, typecode) in reader.toc.items():
        if typecode == 'z':
            validate_toc(reader.open_embedded_archive(name).toc.keys())
    print('[OK] Native Updater archive: no tkinter/Tcl runtime hook:', path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('updater_exe', type=Path)
    args = parser.parse_args()
    try:
        verify(args.updater_exe)
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, '[ERROR] Updater package check failed: %s\n' % exc)


if __name__ == '__main__':
    main()
