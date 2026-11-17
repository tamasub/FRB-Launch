"""Windows filesystem actions for FRB Launch's declarative context menus."""
import ctypes
import base64
from ctypes import wintypes
import os
from pathlib import Path
from filesystem_visibility import is_hidden_attribute
import subprocess

INVALID_WIN_CHARS = set('<>:"/\\|?*')
RESERVED_WIN_NAMES = {'CON', 'PRN', 'AUX', 'NUL',
                      *(f'COM{i}' for i in range(1, 10)),
                      *(f'LPT{i}' for i in range(1, 10))}


def _windows_only():
    if os.name != 'nt':
        raise RuntimeError('Windows専用の操作です')


def show_windows_properties(path):
    """Display Explorer's native property sheet, never FRB Studio.

    SHObjectProperties uses SHOP_FILEPATH for both files and directories.
    """
    _windows_only()
    shell32 = ctypes.WinDLL('shell32', use_last_error=True)
    fn = shell32.SHObjectProperties
    fn.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR]
    fn.restype = wintypes.BOOL
    SHOP_FILEPATH = 0x00000002
    if not fn(None, SHOP_FILEPATH, str(path), None):
        error = ctypes.get_last_error()
        raise OSError(error, 'Windowsのプロパティを表示できませんでした')


def open_with_windows_dialog(path):
    """Choose an application for ONE file using Windows' own Open With UI.

    SHOpenWithDialog delegates registered app discovery and program execution
    to Windows; FRB Launch neither enumerates app handlers nor changes the
    file's default association. OAIF_EXEC opens the chosen app once, and
    OAIF_HIDE_REGISTRATION prevents default-app changes on older Windows.
    """
    _windows_only()
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError('対象ファイルが見つかりません: ' + str(file_path))

    class OPENASINFO(ctypes.Structure):
        _fields_ = [
            ('pcszFile', wintypes.LPCWSTR),
            ('pcszClass', wintypes.LPCWSTR),
            ('oaifInFlags', wintypes.DWORD),
        ]

    shell = ctypes.WinDLL('shell32', use_last_error=True)
    choose = shell.SHOpenWithDialog
    choose.argtypes = [wintypes.HWND, ctypes.POINTER(OPENASINFO)]
    choose.restype = ctypes.c_long  # HRESULT (32-bit signed on Windows)
    options = OPENASINFO(str(file_path.resolve()), None, 0x00000004 | 0x00000020)
    status = choose(None, ctypes.byref(options)) & 0xffffffff
    if status in (0x800704c7, 0x80004004):
        return False  # The user canceled the Windows chooser.
    if status & 0x80000000:
        raise OSError(f'Windowsの「プログラムから開く」を表示できませんでした (0x{status:08X})')
    return True


def open_file_explorer(path):
    _windows_only()
    subprocess.Popen(['explorer.exe', str(path)])


def open_parent_folder(path):
    """Open the containing directory of a filesystem file in Explorer."""
    open_file_explorer(Path(path).parent)


def open_folder_terminal(path):
    _windows_only()
    folder = str(path)
    try:
        subprocess.Popen(['wt.exe', '-d', folder], cwd=folder)
    except FileNotFoundError:
        subprocess.Popen(['powershell.exe', '-NoExit'], cwd=folder)


def open_parent_powershell(path):
    """Open a separate Windows PowerShell window in the selected file's folder.

    Pass cwd separately instead of assembling a PowerShell command. This keeps
    Japanese names, spaces and command metacharacters in paths as plain paths,
    and never executes the selected file itself.
    """
    _windows_only()
    directory = Path(path).resolve().parent
    if not directory.is_dir():
        raise FileNotFoundError('ファイルの親フォルダーが見つかりません: ' + str(directory))
    subprocess.Popen(['powershell.exe', '-NoProfile', '-NoExit'],
                     cwd=str(directory),
                     creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))



def _powershell_literal(value):
    """Quote an arbitrary Windows path as PowerShell single-quoted *data*."""
    return "'" + str(value).replace("'", "''") + "'"


def paused_script_command(path):
    """Return a PowerShell EncodedCommand that retains its own console.

    Do not use cmd /c string interpolation, because files may contain shell
    metacharacters. Run scripts inside a *child* process so script-level exit
    does not bypass the parent's final Read-Host prompt.
    """
    path = Path(path).resolve()
    suffix = path.suffix.casefold()
    if suffix not in ('.ps1', '.py'):
        raise ValueError('Pause付き実行は .ps1 / .py ファイルのみ対象です')
    if not path.is_file():
        raise FileNotFoundError('実行するスクリプトが見つかりません: ' + str(path))
    if not path.parent.is_dir():
        raise FileNotFoundError('スクリプトのフォルダーが見つかりません: ' + str(path.parent))

    # Match the existing file-index execution route (file_index.launch_steps).
    # For .ps1, use a child PowerShell so `exit` inside the script does not
    # close this wrapper before the user can read the output.
    runner = "& powershell.exe -NoProfile -File " if suffix == '.ps1' else "& py.exe -3 "
    # PowerShell may initialize its location independently of CreateProcess's
    # working directory. Set both the PowerShell location and the process cwd
    # before spawning the child interpreter (.ps1 or .py).
    work_dir = _powershell_literal(path.parent)
    command = (
        "$ErrorActionPreference = 'Stop'\n"
        "$exitCode = 1\n"
        "try {\n"
        f"    Set-Location -LiteralPath {work_dir}\n"
        "    [System.Environment]::CurrentDirectory = (Get-Location).ProviderPath\n"
        "    Write-Host '[実行ファイル]'\n"
        f"    Write-Host {_powershell_literal(path)}\n"
        "    Write-Host ''\n"
        "    Write-Host '[作業フォルダー]'\n"
        "    Write-Host ((Get-Location).ProviderPath)\n"
        "    Write-Host ''\n"
        "    Write-Host '-------- 実行開始 --------'\n"
        "    Write-Host ''\n"
        f"    {runner}{_powershell_literal(path)}\n"
        "    $exitCode = $LASTEXITCODE\n"
        "    if ($null -eq $exitCode) { $exitCode = 0 }\n"
        "    Write-Host ''\n"
        "    Write-Host ('[終了コード] ' + $exitCode)\n"
        "} catch {\n"
        "    Write-Host ('[起動エラー] ' + $_.Exception.Message) -ForegroundColor Red\n"
        "} finally {\n"
        "    Write-Host ''\n"
        "    [void](Read-Host '実行終了。Enterでウィンドウを閉じます')\n"
        "}\n"
    )
    encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
    return ['powershell.exe', '-NoProfile', '-NoLogo', '-EncodedCommand', encoded]


def run_script_with_pause(path):
    """Run a local .ps1/.py in a fresh visible PowerShell console and pause."""
    _windows_only()
    command = paused_script_command(path)
    subprocess.Popen(command,
                     cwd=str(Path(path).resolve().parent),
                     creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))


def rename_file_or_folder(path, new_name):
    """Rename in the same directory; never overwrite an existing file/folder."""
    path = Path(path)
    if (not isinstance(new_name, str) or not new_name
            or new_name in ('.', '..') or new_name != new_name.strip()
            or new_name.endswith('.') or any(c in INVALID_WIN_CHARS or ord(c) < 32
                                               for c in new_name)
            or new_name.split('.', 1)[0].upper() in RESERVED_WIN_NAMES):
        raise ValueError('Windowsで利用できないファイル名です')
    destination = path.with_name(new_name)
    # normcase is case-insensitive on Windows. A case-only rename remains valid.
    if os.path.normcase(str(path)) == os.path.normcase(str(destination)):
        if str(path) == str(destination):
            return path
    elif os.path.lexists(destination):
        raise FileExistsError('同じ名前のファイルまたはフォルダーが既に存在します: ' + str(destination))
    path.rename(destination)
    return destination


# Git commit is independent from the selected filesystem file.
# The selected filename supplies ONLY the commit message, not the staging target.
def is_downloads_directory(directory):
    """True only for this user's Downloads folder, never a similarly named subfolder."""
    home = Path(os.environ.get('USERPROFILE') or str(Path.home()))
    try:
        return Path(directory).resolve() == (home / 'Downloads').resolve()
    except (ValueError, OSError):
        return False


def sort_browser_entries(directory):
    """Only Downloads uses descending filesystem modification time."""
    directory = Path(directory)
    entries = [entry for entry in directory.iterdir()
               if not is_hidden_attribute(entry)]
    if not is_downloads_directory(directory):
        return sorted(entries, key=lambda p: (not p.is_dir(), p.name.casefold()))

    def sort_key(entry):
        try:
            mtime = entry.stat().st_mtime_ns
        except OSError:
            mtime = -1
        return (-mtime, entry.name.casefold())

    return sorted(entries, key=sort_key)


def is_downloads_zip(path):
    path = Path(path)
    return path.suffix.casefold() == '.zip' and is_downloads_directory(path.parent)


def _git(repo, *arguments, timeout=30):
    result = subprocess.run(['git', *arguments], cwd=str(repo),
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f'Git {" ".join(arguments[:2])} 失敗: {detail or result.returncode}')
    return result.stdout


def read_git_commit_options(config_path):
    """Load explicit Git commit destinations. No file-path based selection.

    v2 defines named repositories for the UI; no repository is preselected.
    v1 remains readable for legacy API callers, but Launch's UI requires v2.
    """
    import json
    options = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
    if not isinstance(options, dict) or options.get('version') not in (1, 2):
        raise ValueError('Git設定: version=1 または 2 が必要です')
    if not isinstance(options.get('enabled'), bool):
        raise ValueError('Git設定: enabled は真偽値です')
    if not isinstance(options.get('include_untracked', False), bool):
        raise ValueError('Git設定: include_untracked は真偽値です')
    if options['version'] == 1:
        value = options.get('repository_path')
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Git設定: repository_path を指定してください')
        return options

    repositories = options.get('repositories')
    if not isinstance(repositories, list) or not repositories:
        raise ValueError('Git設定: repositories に候補を1件以上登録してください')
    seen_ids, seen_paths = set(), set()
    for item in repositories:
        if not isinstance(item, dict):
            raise ValueError('Git設定: repositories の要素はオブジェクトです')
        for key in ('id', 'name', 'path'):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f'Git設定: repositories の {key} が不正です')
        identifier = item['id'].casefold()
        normalized_path = item['path'].replace('/', '\\').rstrip('\\').casefold()
        if identifier in seen_ids or normalized_path in seen_paths:
            raise ValueError('Git設定: 重複するリポジトリIDまたはパスがあります')
        seen_ids.add(identifier)
        seen_paths.add(normalized_path)
    return options


def selected_git_commit_options(options, repository_id):
    """Choose exactly one explicitly selected configured repository.

    Filename/location of the message source does not influence this selection.
    """
    if not options.get('enabled'):
        raise ValueError('Gitコミット機能は設定で無効になっています')
    if options.get('version') != 2:
        raise ValueError('リポジトリ選択用のGit設定 version=2 が必要です')
    if not isinstance(repository_id, str) or not repository_id:
        raise ValueError('コミット先リポジトリを選択してください')
    matches = [repo for repo in options['repositories'] if repo['id'] == repository_id]
    if len(matches) != 1:
        raise ValueError('選択したリポジトリはGit設定に存在しません')
    return {
        'enabled': True,
        'repository_path': matches[0]['path'],
        'include_untracked': options.get('include_untracked', False),
    }


def git_commit_preview(options):
    """Validate repo and preview the actual tracked/untracked change set."""
    if not options['enabled']:
        raise ValueError('Gitコミット機能は設定で無効になっています')
    if not options.get('repository_path'):
        raise ValueError('コミット先リポジトリを選択してください')
    repository = Path(os.path.expandvars(options['repository_path'])).expanduser().resolve()
    if not repository.is_dir():
        raise ValueError('Gitリポジトリのフォルダーがありません: ' + str(repository))
    top = Path(_git(repository, 'rev-parse', '--show-toplevel').strip()).resolve()
    if top != repository:
        raise ValueError('Git設定はリポジトリのルートを指定してください: ' + str(top))
    untracked_mode = 'all' if options.get('include_untracked', False) else 'no'
    status = _git(repository, '-c', 'core.quotepath=false', 'status', '--porcelain',
                  f'--untracked-files={untracked_mode}')
    lines = [line for line in status.splitlines() if line.strip()]
    if not lines:
        raise ValueError('コミット対象の変更がありません（未追跡ファイルは対象外）')
    return {'repository': repository, 'changes': lines,
            'include_untracked': options.get('include_untracked', False)}


def commit_tracked_changes(repository, message, include_untracked=False):
    """Commit repository changes; selected filename is only the message."""
    if not isinstance(message, str) or not message.strip() or '\n' in message or '\r' in message:
        raise ValueError('コミットメッセージを1行で入力してください')
    repository = Path(repository)
    # Do not let an accidentally reconfigured path cross repository boundaries.
    top = Path(_git(repository, 'rev-parse', '--show-toplevel').strip()).resolve()
    if top != repository.resolve():
        raise ValueError('リポジトリのルートではありません')
    _git(repository, 'add', '-A' if include_untracked else '-u', timeout=60)
    status = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=str(repository),
                            capture_output=True, text=True, errors='replace', timeout=30)
    if status.returncode == 0:
        raise ValueError('ステージングされた変更はありません')
    if status.returncode != 1:
        raise RuntimeError('ステージ差分の確認に失敗しました: ' + status.stderr.strip())
    _git(repository, 'commit', '-m', message.strip(), timeout=120)
    return _git(repository, 'log', '-1', '--format=%h %s').strip()


def move_to_recycle_bin(path):
    """Ask Windows Shell to recycle a file/folder; never use unlink/rmtree.

    FOF_ALLOWUNDO requests Recycle Bin; FOF_WANTNUKEWARNING ensures that
    Windows warns if the location has no recycling support. The UI also asks
    for confirmation before calling this method.
    """
    _windows_only()
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError('削除対象が見つかりません: ' + str(target))
    if target.is_symlink():
        raise ValueError('リンクの削除は対象外です（リンク先の誤削除防止）')
    if not (target.is_file() or target.is_dir()):
        raise ValueError('通常のファイルまたはフォルダーだけ削除できます')

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ('hwnd', wintypes.HWND), ('wFunc', wintypes.UINT),
            ('pFrom', wintypes.LPCWSTR), ('pTo', wintypes.LPCWSTR),
            ('fFlags', wintypes.WORD), ('fAnyOperationsAborted', wintypes.BOOL),
            ('hNameMappings', wintypes.LPVOID), ('lpszProgressTitle', wintypes.LPCWSTR),
        ]

    buffer = ctypes.create_unicode_buffer(str(target.resolve()) + '\0\0')
    request = SHFILEOPSTRUCTW()
    request.wFunc = 0x0003  # FO_DELETE
    request.pFrom = ctypes.cast(buffer, wintypes.LPCWSTR)
    request.fFlags = 0x0040 | 0x4000  # FOF_ALLOWUNDO | FOF_WANTNUKEWARNING
    shell32 = ctypes.WinDLL('shell32', use_last_error=True)
    operation = shell32.SHFileOperationW
    operation.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    operation.restype = ctypes.c_int
    result = operation(ctypes.byref(request))
    if result or request.fAnyOperationsAborted:
        raise OSError(f'ごみ箱への移動が中断・失敗しました (Shell code: {result})')
