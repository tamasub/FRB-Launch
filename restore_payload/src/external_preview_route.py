"""Narrow Files List -> third-column external editor routes.

No changes to file associations. Obsidian is only used for existing notes
inside a directory with an Obsidian vault config; otherwise Markdown Studio
remains the existing fallback. Sakura runs only when an actual executable can
be identified, otherwise normal Files List handling is left intact.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from urllib.parse import quote


@dataclass(frozen=True)
class ExternalPreviewTarget:
    app: str
    path: str
    executable: str = ''

    @property
    def key(self):
        return self.app, self.path.casefold()


def _real_file_from_row(row):
    if not isinstance(row, dict) or row.get('_launch_virtual_node') is not None:
        return None
    raw = row.get('_browse_file') or row.get('_indexed_file') or row.get('_file')
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        file = Path(raw).resolve(strict=True)
        return file if file.is_file() else None
    except (OSError, ValueError, RuntimeError):
        return None


def find_vault_root(file):
    """Detect a local vault without relying on a filename's extension alone.

    The URI handler ultimately decides whether a particular vault is registered.
    Custom Obsidian config dir names aren't autodetected in this first trial.
    """
    for parent in Path(file).parents:
        if (parent / '.obsidian').is_dir():
            return parent
    return None


def find_sakura_executable():
    """Resolve the installed editor, never infer it from the .txt association."""
    environment = os.environ
    explicit = environment.get('FRB_LAUNCH_SAKURA_EXE')
    if explicit:
        exe = Path(os.path.expandvars(explicit.strip().strip('"')))
        return str(exe) if exe.is_file() and exe.name.casefold() == 'sakura.exe' else None
    candidates = []
    path_exe = shutil.which('sakura.exe')
    if path_exe:
        candidates.append(path_exe)
    if os.name == 'nt':
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subkey in (r'Software\Microsoft\Windows\CurrentVersion\App Paths\sakura.exe',):
                    try:
                        with winreg.OpenKey(hive, subkey) as registry_key:
                            candidates.append(winreg.QueryValueEx(registry_key, '')[0])
                    except OSError:
                        continue
            from windows_open_with import discover_open_with_apps
            for app in discover_open_with_apps('trial.txt'):
                if Path(app.executable).name.casefold() == 'sakura.exe':
                    candidates.append(app.executable)
        except (ImportError, OSError, ValueError):
            pass
    for prefix in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        folder = environment.get(prefix)
        if folder:
            for suffix in (('sakura', 'sakura.exe'), ('SakuraEditor', 'sakura.exe'),
                           ('Programs', 'SakuraEditor', 'sakura.exe')):
                candidates.append(str(Path(folder).joinpath(*suffix)))
    for candidate in candidates:
        exe = Path(os.path.expandvars(str(candidate).strip('"')))
        if exe.name.casefold() == 'sakura.exe' and exe.is_file():
            return str(exe)
    return None


def external_preview_target(row, *, sakura_lookup=None, vault_lookup=None):
    """Map only concrete Files List leaves; other actions are never intercepted."""
    path = _real_file_from_row(row)
    if path is None:
        return None
    if path.suffix.casefold() == '.md':
        vault = (vault_lookup or find_vault_root)(path)
        if vault is not None:
            return ExternalPreviewTarget('obsidian', str(path))
        return None  # Preserve existing Markdown Studio for files outside vaults.
    if path.suffix.casefold() in ('.txt', '.ini'):
        executable = (sakura_lookup or find_sakura_executable)()
        if executable:
            return ExternalPreviewTarget('sakura', str(path), executable)
    return None


def obsidian_open_uri(file):
    """Dedicated pop-out window, never hijack the user's main vault window."""
    return 'obsidian://open?path=' + quote(str(file), safe='') + '&paneType=window'


def external_start_command(target):
    if target.app != 'sakura' or not target.executable:
        raise ValueError('Sakura editor executable was not resolved')
    # -- ensures files whose names start with '-' aren't mistaken for flags.
    return [target.executable, '--', target.path]
