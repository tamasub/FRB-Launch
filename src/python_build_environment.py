"""Build interpreter contract shared by Launch and its environment updater."""
from __future__ import annotations

import argparse
import importlib
import platform
import struct
import sys
import sysconfig
from importlib.metadata import version

MIN_MIGRATION_VERSION = (3, 15, 2)


def supports_build(version_info, bits, free_threaded, machine, *, migration=False):
    v = tuple(version_info[:3])
    if bits != 64 or free_threaded:
        return False
    if (3, 10) <= v[:2] <= (3, 14):
        return not migration
    # Windows Qt WebEngine 6.12.0.140 supplies the x64 native runtime.
    return (v[:2] == (3, 15) and v >= MIN_MIGRATION_VERSION
            and machine.casefold() in {"amd64", "x86_64"})


def current_supported(*, migration=False):
    return supports_build(sys.version_info, struct.calcsize("P") * 8,
                          bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
                          platform.machine(), migration=migration)


def verify_dependencies():
    expected = {"PySide6": "6.10.1", "pyinstaller": "6.17.0", "tzdata": "2025.2"}
    if sys.version_info[:2] == (3, 15):
        expected.update({"PySide6": "6.12.0", "pyinstaller": "6.22.3",
                         "PySide6-WebEngine": "6.12.0.140"})
    for package, want in expected.items():
        actual = version(package)
        if actual != want:
            raise RuntimeError(f"{package}: expected {want}, got {actual}")
        print(f"[OK] {package} {actual}", flush=True)
    for name in ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
                 "PySide6.QtNetwork", "PySide6.QtWebEngineCore",
                 "PySide6.QtWebEngineWidgets", "PyInstaller"):
        importlib.import_module(name)
    print("[OK] Qt and WebEngine native imports", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migration", action="store_true")
    parser.add_argument("--dependencies", action="store_true")
    args = parser.parse_args()
    print(f"Python: {sys.version.split()[0]} / {struct.calcsize('P') * 8}bit / {platform.machine()}", flush=True)
    print(f"Path: {sys.executable}", flush=True)
    if not current_supported(migration=args.migration):
        print("[ERROR] Use standard (non-free-threaded) x64 Python 3.15.2 or newer 3.15.x.")
        if not args.migration:
            print("[INFO] Existing standard 64-bit Python 3.10-3.14 environments remain supported.")
        return 1
    if args.dependencies:
        try:
            verify_dependencies()
        except Exception as exc:
            print(f"[ERROR] Dependency validation failed: {exc}", file=sys.stderr, flush=True)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
