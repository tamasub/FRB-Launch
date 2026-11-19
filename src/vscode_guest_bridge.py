"""Opt-in VS Code window for Launch's *non-parenting* third-column overlay.

Never adopt a pre-existing desktop Code.exe HWND. Launch requests a fresh
window under a persistent *Launch-only* user-data directory. VS Code sign-in,
theme, settings and workspace state can survive a restart without sharing the
user's regular VS Code profile. Newly opened HWNDs must still be verified.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil

CODE_SUFFIXES = frozenset({
    '.py', '.pyw', '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
    '.html', '.htm', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',
    '.java', '.c', '.h', '.cpp', '.hpp', '.cs', '.go', '.rs', '.rb', '.php',
    '.sh', '.ps1', '.psm1', '.sql', '.yaml', '.yml', '.xml', '.toml',
    '.json', '.jsonc', '.code-workspace',
})


def enabled(environment=None):
    env = os.environ if environment is None else environment
    return env.get('FRB_VSCODE_GUEST_OVERLAY', '').strip() == '1'


def accepts_file(path):
    return Path(path).suffix.casefold() in CODE_SUFFIXES


def find_executable(environment=None):
    """Find Code.exe; never infer it from a .py file association."""
    env = os.environ if environment is None else environment
    candidates = []
    override = env.get('FRB_LAUNCH_VSCODE_EXE', '').strip().strip('"')
    if override:
        candidates.append(override)
    candidates.append(shutil.which('Code.exe'))
    for variable, pieces in (
        ('LOCALAPPDATA', ('Programs', 'Microsoft VS Code', 'Code.exe')),
        ('ProgramFiles', ('Microsoft VS Code', 'Code.exe')),
        ('ProgramFiles(x86)', ('Microsoft VS Code', 'Code.exe')),
    ):
        if env.get(variable):
            candidates.append(str(Path(env[variable]).joinpath(*pieces)))
    if os.name == 'nt':
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive,
                        r'Software\Microsoft\Windows\CurrentVersion\App Paths\Code.exe') as key:
                        candidates.append(winreg.QueryValueEx(key, '')[0])
                except OSError:
                    pass
        except ImportError:
            pass
    for raw in candidates:
        if raw:
            path = Path(os.path.expandvars(str(raw).strip('"')))
            if path.name.casefold() == 'code.exe' and path.is_file():
                return str(path)
    return None


def new_profile_root(environment=None):
    """Return a stable Launch-only VS Code user-data directory.

    VS Code owns and persists the data; Launch must never delete this folder.
    Reuse this location across restarts to retain OAuth sessions and settings.
    It is deliberately NOT the ordinary desktop VS Code user profile.
    """
    env = os.environ if environment is None else environment
    base = Path(env.get('LOCALAPPDATA') or Path.home()) / 'FRBLaunch' / 'VSCodeGuest'
    return base / 'profile-v1'


def command(executable, profile_dir, path, *, reuse=False):
    """Always select the same isolated VS Code instance, not desktop Code."""
    if not executable or not profile_dir or not path:
        raise ValueError('VS Codeの実行ファイル・専用プロファイル・対象ファイルが必要です')
    return [str(executable), '--user-data-dir', str(profile_dir),
            '--reuse-window' if reuse else '--new-window', str(path)]


def new_hwnd_for_file(windows, baseline, target_file):
    """Choose exactly one *new* Code.exe top-level HWND showing the file.

    Never select by PID alone: Code.exe CLI can reuse an Electron process.
    An empty or ambiguous result must NOT steal an existing user window.
    """
    filename = Path(target_file).name.casefold()
    candidates = [(int(hwnd), int(pid)) for hwnd,pid,title in windows
                  if int(hwnd) not in baseline and int(pid) > 0
                  and filename in title.casefold()]
    return candidates[0][0] if len(candidates) == 1 else None


def caption_matches_file(caption, path):
    return bool(caption and Path(path).name.casefold() in caption.casefold())
