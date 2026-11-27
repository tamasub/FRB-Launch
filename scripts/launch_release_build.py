"""Launch-only version/build coordinator. Integrated release numbering is unrelated."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
DECLARATION = re.compile(rb"(?m)^APP_VERSION[ \t]*=[ \t]*(?P<q>['\"])(?P<v>[0-9]+\.[0-9]+\.[0-9]+)(?P=q)[ \t]*\r?$")
RECEIPT = Path('dist/.frb_launch_build.json')
SOURCE = Path('src/app_version.py')
EXE = Path('dist/FRBLaunch/FRBLaunch.exe')


def source_version(data: bytes):
    matches = list(DECLARATION.finditer(data))
    if len(matches) != 1:
        raise ValueError('Expected exactly one APP_VERSION declaration')
    match = matches[0]
    return match.group('v').decode('ascii'), match.span('v')


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def sha(path: Path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def invalidate(root: Path):
    (root / RECEIPT).unlink(missing_ok=True)


def record(root: Path):
    """Called by the existing BAT only after all build steps have succeeded."""
    data = (root / SOURCE).read_bytes()
    version, _ = source_version(data)
    exe = root / EXE
    if not exe.is_file() or not exe.stat().st_size:
        raise ValueError('Built FRBLaunch.exe missing or empty')
    if (root / SOURCE).stat().st_mtime_ns > exe.stat().st_mtime_ns:
        raise ValueError('APP_VERSION source is newer than the built EXE')
    receipt = {'schema': 'frb-launch-build-v1', 'version': version,
               'source_sha256': hashlib.sha256(data).hexdigest(), 'exe_sha256': sha(exe)}
    atomic_write(root / RECEIPT, (json.dumps(receipt, indent=2) + '\n').encode('utf-8'))
    print('[OK] Build receipt: Launch ' + version, flush=True)
    return receipt


def verify(root: Path, expected: str):
    receipt = json.loads((root / RECEIPT).read_text('utf-8'))
    data = (root / SOURCE).read_bytes()
    current, _ = source_version(data)
    if (receipt.get('schema') != 'frb-launch-build-v1' or
            receipt.get('version') != expected or current != expected or
            receipt.get('source_sha256') != hashlib.sha256(data).hexdigest() or
            receipt.get('exe_sha256') != sha(root / EXE)):
        raise ValueError('Launch source, EXE and build receipt disagree; rebuild')
    return receipt


def run_existing_bat(root: Path):
    env = dict(os.environ, FRB_GUI_BUILD='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    # Fixed BAT name, no user arguments and no duplicated PyInstaller command.
    result = subprocess.run([env.get('ComSpec', 'cmd.exe'), '/d', '/c', '_build_windows.bat'],
                            cwd=root, env=env, stdin=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return result.returncode


def build(root: Path, expected: str, target: str, runner=run_existing_bat):
    if not VERSION.fullmatch(expected) or not VERSION.fullmatch(target):
        raise ValueError('Invalid Launch version')
    if not (root / '_build_windows.bat').is_file():
        raise FileNotFoundError('_build_windows.bat')
    file = root / SOURCE
    data = file.read_bytes()
    current, (start, end) = source_version(data)
    if current != expected:
        raise ValueError(f'Launch source changed: expected {expected}, got {current}; refresh GUI')
    if tuple(map(int, target.split('.'))) < tuple(map(int, current.split('.'))):
        raise ValueError('Launch version downgrade is not allowed')
    # No previous successful build may authorize release if this attempt fails.
    invalidate(root)
    try:
        if current != target:
            atomic_write(file, data[:start] + target.encode('ascii') + data[end:])
        print(f'[VERSION] Launch {current} -> {target}', flush=True)
        code = runner(root)
        if code:
            raise RuntimeError(f'_build_windows.bat failed (exit {code})')
        verify(root, target)
        print(f'[OK] Launch build {target} verified', flush=True)
    except BaseException:
        invalidate(root)
        # Keep the selected version. Retry with Keep; never silently increment again.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'record'))
    parser.add_argument('--expected', default='')
    parser.add_argument('--target', default='')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.action == 'record':
            record(root)
        else:
            build(root, args.expected, args.target)
    except Exception as exc:
        print(f'[ERROR] {exc}', file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
