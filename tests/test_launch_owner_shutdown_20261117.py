"""NativeShell identity and unsaved-safe Launch lifecycle (no Windows dependency)."""
import ast
import io
from pathlib import Path
from types import SimpleNamespace as NS
import sys

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
from studio_launch_lifecycle import close_owned_studio, LAUNCH_CLOSE_COMMAND


class Pipe(io.BytesIO):
    def __init__(self, response):
        super().__init__((response + '\n').encode('utf-8'))
        self.written = []
    def write(self, value):
        self.written.append(value)
        return len(value)


class Proc:
    def __init__(self, alive=True):
        self.alive = alive
        self.wait_calls = []
    def poll(self):
        return None if self.alive else 0
    def wait(self, timeout):
        self.wait_calls.append(timeout)
        self.alive = False


def test_private_pipe_close_waits_for_owned_process_and_never_kills():
    process = Proc()
    pipe = Pipe('OK')
    token = '1234abcd' * 4
    opened = []
    def opener(name, *args, **kwargs):
        opened.append(name)
        return pipe
    assert close_owned_studio(process, token, opener=opener) == 'OK'
    assert opened == [r'\\.\pipe\frb_studio_launch_' + token]
    assert pipe.written == [(LAUNCH_CLOSE_COMMAND + '\n').encode()]
    assert process.wait_calls == [10]


def test_cancel_preserves_live_native_shell():
    process = Proc()
    result = close_owned_studio(process, 'a' * 32, opener=lambda *a, **k: Pipe('CANCEL'))
    assert result == 'CANCEL'
    assert process.alive and process.wait_calls == []


def test_no_token_never_touches_unrelated_process():
    process = Proc()
    assert close_owned_studio(process, 'bad', opener=lambda *args, **kwargs: 1/0).startswith('ERROR:')
    assert process.alive
    process.alive = False
    assert close_owned_studio(process, 'bad', opener=lambda *args, **kwargs: 1/0) == 'OK'


def test_owner_pid_and_normal_quit_are_wired_correctly():
    panel = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
    expanded = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    assert "'--launch-preview-owner-pid=' + str(os.getpid())" in panel
    method = expanded.split('    def release_studio_preview(self):', 1)[1].split('    def show_files_view(', 1)[0]
    assert method.index('panel.close_launch_owned_studio()') < method.index('self.studio_preview.undock()')
    assert 'if not panel.close_launch_owned_studio():' in method
    assert 'return False' in method


def test_width_persistence_is_flushed_before_abrupt_console_close():
    source = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ExpandedLauncherView')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_save_active_preview_width')
    scope = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<width-save>', 'exec'), scope)
    writes = {}
    sync_calls = []
    settings = NS(setValue=lambda k,v: writes.__setitem__(k,v), sync=lambda: sync_calls.append('sync'))
    panel = NS(isHidden=lambda: False)
    splitter = NS(indexOf=lambda p: 3, sizes=lambda: [300, 380, 0, 520])
    view = NS(studio_preview=panel, browser_preview=None, files_splitter=splitter,
              launcher=NS(settings=settings), _preview_layout_restoring=True)
    scope['_save_active_preview_width'](view)
    assert not writes
    view._preview_layout_restoring = False
    scope['_save_active_preview_width'](view)
    assert writes['workspace_files_studio_preview_width'] == 520
    assert writes['workspace_files_preview_width'] == 520
    assert sync_calls == ['sync']


def test_native_owner_shutdown_contract_static():
    native = (Path(__file__).resolve().parents[2] / 'studio_latest' / 'NativeShell' / 'NativeShellForm.cs')
    # Test may also run in standalone Launch without Studio checkout.
    if not native.is_file():
        return
    form = native.read_text(encoding='utf-8')
    assert 'StartLaunchOwnerWatch()' in form
    assert 'owner.WaitForExit()' in form
    assert 'ExposeOrphanedLaunchStudio();' in form
    assert 'ConfirmLaunchPreviewLeaveAsync()' in form
    assert 'requestedPath == LaunchCloseCommand && result == "OK"' in form
