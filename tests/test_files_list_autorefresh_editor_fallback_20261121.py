"""Regression tests for two opt-in-safe user-facing changes.

Qt-free: production watcher handlers are extracted from their AST so these run
on CI that does not have PySide6.  Windows D&D and actual OS notification
still require real Windows acceptance testing.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from external_preview_route import (
    ExternalPreviewTarget, dedicated_editor_available,
    launch_external_standalone, external_preview_target,
)

ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / 'src' / 'expanded_view.py').read_text(encoding='utf-8')


def production_method(name):
    module = ast.parse(VIEW)
    klass = next(c for c in module.body if isinstance(c, ast.ClassDef)
                 and c.name == 'ExpandedLauncherView')
    node = next(f for f in klass.body if isinstance(f, ast.FunctionDef)
                and f.name == name)
    ns = {'os': os,
          'QAbstractItemView': NS(State=NS(EditingState=1, DraggingState=2))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],
                                                type_ignores=[])), '<source>', 'exec'), ns)
    return ns[name]


class FakeTimer:
    def __init__(self):
        self.starts = 0
        self.stops = 0
    def start(self): self.starts += 1
    def stop(self): self.stops += 1


class FakeWatcher:
    def __init__(self): self.paths = []
    def directories(self): return self.paths[:]
    def addPath(self, path):
        self.paths.append(path)
        return True
    def removePath(self, path):
        self.paths.remove(path)
        return True


def fake_view(directory):
    watcher, timer = FakeWatcher(), FakeTimer()
    path = [directory]
    view = NS(_file_list_directory_watcher=watcher,
              _file_list_watched_directory='',
              _file_list_refresh_pending_path='',
              _file_list_refresh_timer=timer,
              _workspace_mode='files', _virtual_directory_node=None,
              _refreshing=False,
              launcher=NS(_filesystem_dialog_depth=0),
              middle=NS(tree=NS(state=lambda: 0)),
              isVisible=lambda: True,
              current_directory=lambda: path[0])
    view._sync_file_list_directory_watch = lambda: production_method(
        '_sync_file_list_directory_watch')(view)
    view._queue_file_list_auto_refresh = lambda p: production_method(
        '_queue_file_list_auto_refresh')(view, p)
    view._flush_file_list_auto_refresh = lambda: production_method(
        '_flush_file_list_auto_refresh')(view)
    return view, watcher, timer, path


def test_watcher_follows_one_physical_directory_and_ignores_virtual(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'
    a.mkdir(); b.mkdir()
    view, watcher, _, path = fake_view(str(a))
    view._sync_file_list_directory_watch()
    assert watcher.paths == [os.path.normcase(os.path.abspath(a))]
    view._sync_file_list_directory_watch()  # no duplicate
    assert len(watcher.paths) == 1
    path[0] = str(b)
    view._sync_file_list_directory_watch()
    assert watcher.paths == [os.path.normcase(os.path.abspath(b))]
    view._virtual_directory_node = {'kind': 'virtual'}
    view._sync_file_list_directory_watch()
    assert watcher.paths == []


def test_auto_refresh_coalesces_and_reuses_f5_without_exp_navigation(tmp_path):
    folder = tmp_path / 'a'; folder.mkdir()
    view, watcher, timer, _ = fake_view(str(folder))
    view._sync_file_list_directory_watch()
    calls = []
    def refresh():
        assert view._in_place_files_refresh is True
        calls.append('f5')
        return True
    view.refresh_current_directory = refresh
    view._queue_file_list_auto_refresh(str(folder))
    view._queue_file_list_auto_refresh(str(folder))
    assert calls == [] and timer.starts == 2
    view._flush_file_list_auto_refresh()
    assert calls == ['f5']
    assert view._in_place_files_refresh is False
    assert view._file_list_refresh_pending_path == ''


def test_auto_refresh_does_not_destroy_inline_rename_or_drag(tmp_path):
    folder = tmp_path / 'a'; folder.mkdir()
    view, _, timer, _ = fake_view(str(folder))
    view._sync_file_list_directory_watch()
    view.refresh_current_directory = lambda: pytest.fail('should not refresh')
    view._queue_file_list_auto_refresh(str(folder))
    for state in (1, 2):
        view.middle.tree.state = lambda state=state: state
        view._flush_file_list_auto_refresh()
        assert view._file_list_refresh_pending_path
    assert timer.starts >= 3
    view.middle.tree.state = lambda: 0
    calls = []
    view.refresh_current_directory = lambda: calls.append('refresh')
    view._flush_file_list_auto_refresh()
    assert calls == ['refresh']


def test_old_folder_notification_does_not_refresh_current_folder(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'
    a.mkdir(); b.mkdir()
    view, watcher, _, path = fake_view(str(a))
    view._sync_file_list_directory_watch()
    path[0] = str(b)
    view._sync_file_list_directory_watch()
    view._queue_file_list_auto_refresh(str(a))
    assert not view._file_list_refresh_pending_path
    assert watcher.paths == [os.path.normcase(os.path.abspath(b))]


def test_view_wires_directory_signal_without_replacing_f5():
    assert 'QFileSystemWatcher(self)' in VIEW
    assert 'directoryChanged.connect(\n            self._queue_file_list_auto_refresh)' in VIEW
    assert 'self._file_list_refresh_timer.setInterval(300)' in VIEW
    assert 'self.refresh_current_directory()  # F5 logic' in VIEW
    assert 'if enabled and dedicated_editor_available(external)' in VIEW
    assert 'if restored_current is None and previous_index >= 0' in VIEW


def test_missing_obsidian_uses_file_association_without_embedded_guest(tmp_path):
    note = tmp_path / '日本語.md'; note.write_text('test', encoding='utf-8')
    target = ExternalPreviewTarget('obsidian', str(note))
    assert dedicated_editor_available(target, obsidian_lookup=lambda: None) is False
    calls = []
    launch_external_standalone(target, obsidian_lookup=lambda: None,
                               startfile=lambda p: calls.append(p),
                               popen=lambda *a, **kw: pytest.fail('no executable'))
    assert calls == [str(note)]


def test_installed_obsidian_stays_on_existing_command_route(tmp_path):
    exe = tmp_path / 'Obsidian.exe'; exe.write_bytes(b'bin')
    note = tmp_path / 'note.md'; note.write_text('note')
    target = ExternalPreviewTarget('obsidian', str(note))
    cmds = []
    launch_external_standalone(target, obsidian_lookup=lambda: str(exe),
                               startfile=lambda p: pytest.fail('unexpected fallback'),
                               popen=lambda cmd, **kw: cmds.append(cmd))
    assert cmds == [[str(exe), str(note)]]


def test_missing_vscode_uses_default_app_without_changing_studio_json(tmp_path, monkeypatch):
    from vscode_guest_bridge import find_executable
    import vscode_guest_bridge
    monkeypatch.setattr(vscode_guest_bridge, 'find_executable', lambda: None)
    code = tmp_path / 'hello.py'; code.write_text('print(1)')
    target = ExternalPreviewTarget('vscode', str(code))
    assert not dedicated_editor_available(target)
    opened = []
    launch_external_standalone(target, startfile=lambda p: opened.append(p))
    assert opened == [str(code)]
    assert "studio_managed_json(path, Path(studio_root))" in (
        ROOT / 'src' / 'external_preview_route.py').read_text(encoding='utf-8')


def test_missing_sakura_falls_back_to_default_route(tmp_path):
    txt = tmp_path / 'note.txt'; txt.write_text('hi')
    assert external_preview_target({'_browse_file': str(txt)},
                                   sakura_lookup=lambda: None) is None
    target = ExternalPreviewTarget('sakura', str(txt), str(tmp_path / 'sakura.exe'))
    opened = []
    launch_external_standalone(target, startfile=lambda p: opened.append(p))
    assert opened == [str(txt)]


def test_missing_binary_after_check_falls_back_but_permission_error_is_reported(tmp_path):
    exe = tmp_path / 'Obsidian.exe'; exe.write_bytes(b'bin')
    note = tmp_path / 'note.md'; note.write_text('test')
    target = ExternalPreviewTarget('obsidian', str(note))
    events = []
    def removed(*args, **kwargs):
        raise FileNotFoundError('removed')
    launch_external_standalone(target, obsidian_lookup=lambda: str(exe),
                               popen=removed, startfile=events.append)
    assert events == [str(note)]
    def denied(*args, **kwargs):
        raise PermissionError('access denied')
    with pytest.raises(PermissionError):
        launch_external_standalone(target, obsidian_lookup=lambda: str(exe),
                                   popen=denied, startfile=events.append)
    assert events == [str(note)]
