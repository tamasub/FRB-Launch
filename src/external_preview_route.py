"""Route physical Files List .md/.txt/.ini/.log to their requested editors.

Embedding in Launch is optional; the application selection is independent of
Vault membership and file associations. Studio JSON routing is separate.
"""
from dataclasses import dataclass
import os
import json
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


def _obsidian_vault_registry_path():
    """Desktop Obsidian's registered vault list, not a guessed .obsidian dir."""
    appdata = os.environ.get('APPDATA', '')
    return Path(appdata) / 'obsidian' / 'obsidian.json' if appdata else None


def registered_obsidian_vaults(registry_path=None):
    """Read Obsidian's own vault registry; fail closed on absent/bad settings.

    Creating a .obsidian directory alone does NOT register a vault with the
    obsidian:// URI handler.  Don't send such paths to Obsidian because it
    displays a modal 'Vault not found' dialog and can destabilize embedding.
    """
    path = registry_path if registry_path is not None else _obsidian_vault_registry_path()
    if path is None:
        return ()
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        entries = data.get('vaults', {})
        if not isinstance(entries, dict):
            return ()
        roots = []
        for item in entries.values():
            if not isinstance(item, dict) or not isinstance(item.get('path'), str):
                continue
            root = Path(item['path']).resolve(strict=True)
            if root.is_dir():
                roots.append(root)
        return tuple(roots)
    except (OSError, ValueError, TypeError, RuntimeError):
        return ()


def find_vault_root(file, *, registered_roots=None):
    """Return the most specific *registered* vault containing this note.

    Obsidian URI `open?path=...` resolves only vaults in its own registry.
    Prefer registered-vault membership over looking for a mere .obsidian folder.
    """
    try:
        note = Path(file).resolve(strict=True)
        roots = (registered_obsidian_vaults() if registered_roots is None
                 else tuple(Path(root).resolve(strict=True) for root in registered_roots))
        candidates = [root for root in roots if note.is_relative_to(root)]
        return max(candidates, key=lambda root: len(root.parts), default=None)
    except (OSError, ValueError, TypeError, RuntimeError):
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


def external_preview_target(row, *, sakura_lookup=None, vault_lookup=None, studio_root=None):
    """Map only concrete Files List leaves; other actions are never intercepted."""
    path = _real_file_from_row(row)
    if path is None:
        return None
    if path.suffix.casefold() == '.md':
        return ExternalPreviewTarget('obsidian', str(path))
    if path.suffix.casefold() in ('.txt', '.ini', '.log'):
        executable = (sakura_lookup or find_sakura_executable)()
        if executable:
            return ExternalPreviewTarget('sakura', str(path), executable)
    # Trial-only route: no changes to Studio JSON, Obsidian Markdown, or Sakura.
    from vscode_guest_bridge import enabled, accepts_file
    if enabled() and accepts_file(path):
        if path.suffix.casefold() == '.json':
            # Managed JSON must continue to use FRB Studio. Without the
            # active Studio root we cannot safely decide; fail closed.
            if not studio_root:
                return None
            from file_index import studio_managed_json
            if studio_managed_json(path, Path(studio_root)):
                return None
        return ExternalPreviewTarget('vscode', str(path))
    return None


def obsidian_open_uri(file, *, require_registered=False):
    """Open a note in the main Obsidian vault window (never a pop-out).

    The documented `path=` URI searches vaults again inside Obsidian and can
    show "Vault not found" for a registered-but-ambiguous absolute path.
    Use the registry's stable vault ID and a relative note path instead.
    A non-registered path keeps the legacy URI for callers of this utility;
    normal Files List routing never launches an unregistered vault.
    """
    note = Path(file)
    registry_path = _obsidian_vault_registry_path()
    if registry_path is not None:
        try:
            note = note.resolve(strict=True)
            data = json.loads(registry_path.read_text(encoding='utf-8-sig'))
            candidates = []
            for vault_id, item in data.get('vaults', {}).items():
                if not isinstance(item, dict) or not isinstance(item.get('path'), str):
                    continue
                root = Path(item['path']).resolve(strict=True)
                if root.is_dir() and note.is_relative_to(root):
                    candidates.append((len(root.parts), str(vault_id), note.relative_to(root)))
            if candidates:
                _, vault_id, relative = max(candidates, key=lambda candidate: candidate[0])
                return ('obsidian://open?vault=' + quote(vault_id, safe='') +
                        '&file=' + quote(relative.as_posix(), safe=''))
        except (OSError, ValueError, TypeError, RuntimeError, AttributeError):
            pass
    if require_registered:
        raise ValueError('Obsidianに登録済みのVaultが見つかりません。Markdown Studioで開いてください。')
    return 'obsidian://open?path=' + quote(str(file), safe='')


def external_start_command(target):
    if target.app != 'sakura' or not target.executable:
        raise ValueError('Sakura editor executable was not resolved')
    # -- ensures files whose names start with '-' aren't mistaken for flags.
    return [target.executable, '--', target.path]


def find_obsidian_executable():
    """Find the official Windows executable without using .md file association."""
    explicit = os.environ.get('FRB_LAUNCH_OBSIDIAN_EXE', '').strip().strip('"')
    if explicit:
        candidate = Path(os.path.expandvars(explicit))
        return str(candidate) if candidate.is_file() else None
    candidates = [shutil.which('Obsidian.exe')]
    for variable, suffixes in (
            ('LOCALAPPDATA', (('Programs', 'Obsidian', 'Obsidian.exe'),)),
            ('ProgramFiles', (('Obsidian', 'Obsidian.exe'),)),
            ('ProgramFiles(x86)', (('Obsidian', 'Obsidian.exe'),))):
        base = os.environ.get(variable)
        if base:
            candidates.extend(str(Path(base).joinpath(*s)) for s in suffixes)
    if os.name == 'nt':
        try:
            import winreg
            key_name = r'Software\Microsoft\Windows\CurrentVersion\App Paths\Obsidian.exe'
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        candidates.append(winreg.QueryValueEx(key, '')[0])
                except OSError:
                    continue
        except ImportError:
            pass
    for item in candidates:
        if item:
            candidate = Path(os.path.expandvars(str(item).strip('"')))
            if candidate.is_file() and candidate.name.casefold() == 'obsidian.exe':
                return str(candidate)
    return None


def dedicated_editor_available(target, *, obsidian_lookup=None, vscode_lookup=None):
    """Only attempt an embedded guest when its native executable exists.

    A missing executable should not reserve the third column or display an
    editor error; the normal Windows file association remains the fallback.
    """
    if target.app == 'sakura':
        return bool(target.executable and Path(target.executable).is_file())
    if target.app == 'obsidian':
        return bool((obsidian_lookup or find_obsidian_executable)())
    if target.app == 'vscode':
        from vscode_guest_bridge import find_executable
        return bool((vscode_lookup or find_executable)())
    return True


def _open_with_windows_default(path, *, startfile=None):
    """Open a physical document via its Windows association, never execute a shell."""
    if not Path(path).is_file():
        raise FileNotFoundError(f'対象ファイルが見つかりません: {path}')
    opener = startfile if startfile is not None else getattr(os, 'startfile', None)
    if opener is None:
        raise OSError('Windows標準アプリによるファイル起動はWindows専用です')
    return opener(str(path))


def standalone_editor_command(target, *, obsidian_lookup=None):
    """Return the executable command; no implicit Studio or default-app fallback."""
    if target.app == 'sakura':
        return external_start_command(target)
    if target.app == 'obsidian':
        executable = (obsidian_lookup or find_obsidian_executable)()
        if not executable:
            raise FileNotFoundError('Obsidian.exeが見つかりません（最新版を再インストールしてください）')
        # Obsidian 1.14+ with a current installer supports standalone .md.
        # Passing an explicit absolute path keeps Vault-outside files intact.
        return [executable, target.path]
    if target.app == 'vscode':
        from vscode_guest_bridge import find_executable
        executable = find_executable()
        if not executable:
            raise FileNotFoundError('Visual Studio Code (Code.exe) が見つかりません')
        return [executable, target.path]  # Failure fallback: ordinary desktop open.
    raise ValueError('サポートされていない外部エディターです')


def launch_external_standalone(target, *, popen=None, obsidian_lookup=None,
                               startfile=None):
    """Prefer an installed editor; otherwise use the Windows default app.

    No shell commands, no change to associations and no fallback on a generic
    launch failure (such as access denied). Missing binaries only.
    """
    import subprocess
    if not dedicated_editor_available(target, obsidian_lookup=obsidian_lookup):
        return _open_with_windows_default(target.path, startfile=startfile)
    try:
        command = standalone_editor_command(target, obsidian_lookup=obsidian_lookup)
        return (popen or subprocess.Popen)(command,
                                          cwd=str(Path(command[0]).parent))
    except FileNotFoundError:
        # Removed/uninstalled after discovery, including a stale Sakura path.
        return _open_with_windows_default(target.path, startfile=startfile)
