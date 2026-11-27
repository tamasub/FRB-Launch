"""Explicit, no-default Git destination selection, independent of message filename."""
import ast
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from context_menu_actions import (read_git_commit_options, selected_git_commit_options,
                                  git_commit_preview, commit_tracked_changes)


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def prepare_repo(path):
    path.mkdir()
    git(path, 'init', '-q')
    git(path, 'config', 'user.name', 'Test')
    git(path, 'config', 'user.email', 'test@example.test')
    (path/'info.txt').write_text('initial', encoding='utf-8')
    git(path, 'add', 'info.txt')
    git(path, 'commit', '-qm', 'initial')


def config(tmp_path, paths):
    path = tmp_path / 'options.json'
    path.write_text(json.dumps({
        'version': 2, 'enabled': True, 'include_untracked': True,
        'repositories': [{'id': key, 'name': key.upper(), 'path': str(repo)}
                         for key, repo in paths.items()]
    }), encoding='utf-8')
    return read_git_commit_options(path)


def test_config_contains_three_explicit_destinations():
    options = read_git_commit_options(ROOT/'config/git_commit_options.json')
    assert options['version'] == 2
    assert [i['id'] for i in options['repositories']] == ['frb', 'studio', 'launch']
    assert [i['path'] for i in options['repositories']] == [
        r'F:\FRB', r'F:\FRB_Apps\FRB_Studio', r'F:\FRB_Apps\FRB_Launch']
    assert 'repository_path' not in options  # No implicit default.


def test_selection_is_mandatory_and_explicit(tmp_path):
    one = tmp_path/'repo1'
    two = tmp_path/'repo2'
    prepare_repo(one)
    prepare_repo(two)
    options = config(tmp_path, {'frb': one, 'launch': two})
    with pytest.raises(ValueError, match='選択'):
        selected_git_commit_options(options, '')
    with pytest.raises(ValueError, match='存在しません'):
        selected_git_commit_options(options, 'not-listed')
    selected = selected_git_commit_options(options, 'launch')
    assert selected['repository_path'] == str(two)
    (one/'info.txt').write_text('do not commit', encoding='utf-8')
    (two/'info.txt').write_text('only selected repo', encoding='utf-8')
    preview = git_commit_preview(selected)
    assert preview['repository'] == two
    commit_tracked_changes(preview['repository'], 'some-file-from-other-repo.zip',
                           include_untracked=preview['include_untracked'])
    assert git(two, 'log', '-1', '--format=%s') == 'some-file-from-other-repo.zip'
    assert git(one, 'log', '-1', '--format=%s') == 'initial'


class Dialog:
    def __init__(self, parent):
        self.parent = parent
    def setWindowTitle(self, value): pass
    def setMinimumWidth(self, value): pass
    def resize(self, *args): pass
    def sizeHint(self):
        return SimpleNamespace(height=lambda: 100)
    def accept(self): pass
    def reject(self): pass


class Layout:
    def __init__(self, parent): pass
    def setContentsMargins(self, *args): pass
    def setSpacing(self, spacing): pass
    def addWidget(self, widget): pass


class Combo:
    def __init__(self, parent):
        self.entries = []
        self.index = 0
    def setMinimumWidth(self, value): pass
    def addItem(self, text, data): self.entries.append((text, data))
    def setCurrentIndex(self, value): self.index = value
    def currentData(self): return self.entries[self.index][1]


class Line:
    def __init__(self, parent): self.value = ''
    def setText(self, value): self.value = value
    def setMinimumWidth(self, value): pass
    def selectAll(self): pass
    def text(self): return self.value


class Buttons:
    StandardButton = SimpleNamespace(Ok=1, Cancel=2)
    def __init__(self, *args):
        self.accepted = SimpleNamespace(connect=lambda cb: None)
        self.rejected = SimpleNamespace(connect=lambda cb: None)


def method(name):
    source = ast.parse((ROOT/'src/app.py').read_text(encoding='utf-8'))
    launcher = next(node for node in source.body
                    if isinstance(node, ast.ClassDef) and node.name == 'Launcher')
    fn = next(node for node in launcher.body
              if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {
        'Path': Path,
        'read_git_commit_options': read_git_commit_options,
        'selected_git_commit_options': selected_git_commit_options,
        'git_commit_preview': git_commit_preview,
        'commit_tracked_changes': commit_tracked_changes,
        'GIT_COMMIT_OPTIONS': None,
        'QDialog': Dialog,
        'QVBoxLayout': Layout,
        'QLabel': lambda text, dialog: text,
        'QComboBox': Combo,
        'QLineEdit': Line,
        'QDialogButtonBox': Buttons,
        'QMessageBox': SimpleNamespace(StandardButton=SimpleNamespace(Yes=1)),
        'DIAG': SimpleNamespace(exception=Mock()),
        'subprocess': subprocess,
        'FilesOperationProgress': object(),
        'MESSAGE': 'MESSAGE',
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<test dialog>', 'exec'), scope)
    return scope[name], scope


@pytest.mark.parametrize('choice,should_commit', [(0, False), (3, True)])
def test_dialog_requires_human_choice(tmp_path, choice, should_commit):
    frb = tmp_path/'frb'
    studio = tmp_path/'studio'
    launch = tmp_path/'launch'
    for repo in (frb, studio, launch): prepare_repo(repo)
    for repo in (frb, launch):
        (repo/'info.txt').write_text('changed', encoding='utf-8')
    selected_file = tmp_path/'FRB_Studio_999.zip'
    selected_file.write_text('dummy')
    opts = config(tmp_path, {'frb': frb, 'studio': studio, 'launch': launch})
    method_fn, scope = method('git_commit_using_filename')
    scope['read_git_commit_options'] = lambda _: opts
    preview_calls = []
    def preview(options):
        preview_calls.append(options['repository_path'])
        return git_commit_preview(options)
    scope['git_commit_preview'] = preview
    background_calls = []
    def run_background(callback, mode, **kwargs):
        background_calls.append((mode, kwargs))
        return callback()
    scope['processing_display'] = lambda factory: SimpleNamespace(run_background=run_background)
    def run_dialog(dialog, buttons, editor, *, wheel_combo=None):
        assert wheel_combo is editor
        assert editor.entries[0][1] == ''
        editor.index = choice
        return True
    host = SimpleNamespace(
        run_launch_button_dialog=run_dialog,
        ask_remote_confirmation=lambda *args, **kwargs: 1,
        info_notice=Mock(), error=Mock())
    method_fn(host, selected_file)
    if should_commit:
        assert preview_calls == [str(launch)]
        assert git(launch, 'log', '-1', '--format=%s') == selected_file.name
        host.info_notice.assert_called_once()
        host.error.assert_not_called()
        assert background_calls == [('MESSAGE', {'verb': 'Gitコミット', 'parent': host})]
    else:
        assert preview_calls == []
        assert background_calls == []
        assert '選択' in host.error.call_args.args[0]
    assert git(frb, 'log', '-1', '--format=%s') == 'initial'
    if not should_commit:
        assert git(launch, 'log', '-1', '--format=%s') == 'initial'
