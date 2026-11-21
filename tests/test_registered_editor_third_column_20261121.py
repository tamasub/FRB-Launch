"""Registered JSON menu shortcuts use the existing third-column editors.

No Win32 GUI is exercised here; focus/IME/overlay must be smoke-tested on Win11.
"""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
import external_preview_route
import vscode_guest_bridge
from registered_editor_preview import registered_editor_preview

ROOT = Path(__file__).resolve().parents[1]


def test_authored_open_md_txt_ini_and_code_route_to_expected_editor(tmp_path, monkeypatch):
    sakura = tmp_path / 'sakura.exe'
    sakura.write_bytes(b'')
    monkeypatch.setattr(external_preview_route, 'find_sakura_executable', lambda: str(sakura))
    monkeypatch.setattr(vscode_guest_bridge, 'enabled', lambda: True)
    for extension, expected in [('.md', 'obsidian'), ('.txt', 'sakura'),
                                ('.ini', 'sakura'), ('.js', 'vscode')]:
        document = tmp_path / ('日本語' + extension)
        document.write_text('test', encoding='utf-8')
        result = registered_editor_preview({'launch_action_type': 'Open',
                                            'launch_target': str(document)}, '')
        assert result.kind == 'external'
        assert result.target.app == expected
        assert result.target.path == str(document)


def test_managed_json_uses_studio_and_nonmanaged_uses_vscode(tmp_path, monkeypatch):
    monkeypatch.setattr(vscode_guest_bridge, 'enabled', lambda: True)
    root = tmp_path / 'studio'
    (root / 'defs' / 'work').mkdir(parents=True)
    (root / 'defs' / 'work' / 'schema.json').write_text('{}', encoding='utf-8')
    exe = root / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'')
    managed = tmp_path / 'managed.json'
    managed.write_text('{"view_def":"work/schema.json"}', encoding='utf-8')
    other = tmp_path / 'other.json'
    other.write_text('{}', encoding='utf-8')
    action = lambda f: {'launch_action_type': 'Open', 'launch_target': str(f)}
    studio_preview = registered_editor_preview(action(managed), str(root))
    assert studio_preview.kind == 'studio' and studio_preview.target[0] == str(managed)
    vscode_preview = registered_editor_preview(action(other), str(root))
    assert vscode_preview.kind == 'external' and vscode_preview.target.app == 'vscode'


def test_explicit_run_sakura_and_other_editors(tmp_path):
    sakura = tmp_path / 'sakura.exe'
    sakura.touch()
    ini = tmp_path / 'a.ini'
    ini.write_text('a=b', encoding='utf-8')
    for args in ([str(ini)], ['--', str(ini)]):
        preview = registered_editor_preview({'launch_action_type':'Run',
                                             'launch_program':str(sakura),
                                             'launch_arguments':args}, '')
        assert preview.kind == 'external' and preview.target.app == 'sakura'
        assert preview.target.executable == str(sakura)
    md = tmp_path / 'readme.md'
    md.write_text('test', encoding='utf-8')
    obsidian = registered_editor_preview({'launch_action_type': 'Run',
                                          'launch_program': 'Obsidian.exe',
                                          'launch_arguments': [str(md)]})
    assert obsidian.kind == 'external' and obsidian.target.app == 'obsidian'
    code = registered_editor_preview({'launch_action_type': 'Run',
                                      'launch_program': 'Code.exe',
                                      'launch_arguments': [str(ini)]})
    assert code is None  # This route keeps .ini with Sakura.
    markdown = registered_editor_preview({'launch_action_type': 'Run',
                   'launch_program': str(sakura), 'launch_arguments':[str(md)]})
    assert markdown.kind == 'external' and markdown.target.app == 'sakura'


def test_studio_explicit_run_preserves_launch_metadata(tmp_path):
    exe = tmp_path / 'FRB Studio' / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
    exe.parent.mkdir(parents=True)
    exe.touch()
    file = tmp_path / 'config.json'
    file.write_text('{}', encoding='utf-8')
    preview = registered_editor_preview({'launch_action_type': 'Run',
                 'launch_program': str(exe),
                 'launch_arguments': ['--open-json=' + str(file), '--launch-item-id=i42']})
    assert preview.kind == 'studio'
    assert preview.target[0] == str(file)
    assert preview.target[3] == ('--launch-item-id=i42',)


@pytest.mark.parametrize('step', [
    {'launch_action_type': 'Open', 'launch_target':'https://example.org/a.md'},
    {'launch_action_type': 'Open', 'launch_target':'shell:Downloads'},
    {'launch_action_type': 'Run', 'launch_program':'python.exe', 'launch_arguments':['x.py']},
    {'launch_action_type': 'Run', 'launch_program':'sakura.exe', 'launch_arguments':[]},
    {'launch_action_type': 'Run', 'launch_program':'Code.exe', 'launch_arguments':['--diff','a','b']},
    {'launch_action_type': 'SendKey', 'launch_text':'test'},
])
def test_unrelated_actions_never_redirect(step):
    assert registered_editor_preview(step) is None


def test_authored_browser_open_and_script_open_keep_old_behavior(tmp_path):
    doc = tmp_path / 'test.md'
    doc.write_text('x', encoding='utf-8')
    py = tmp_path / 'test.py'
    py.write_text('print(1)', encoding='utf-8')
    assert registered_editor_preview({'launch_action_type':'Open',
                'launch_target':str(doc), 'launch_browser':'chrome'}) is None
    assert registered_editor_preview({'launch_action_type':'Open',
                'launch_target':str(py)}) is None


def _launcher_method(name):
    source = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    launcher = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == 'Launcher')
    node = next(f for f in launcher.body if isinstance(f, ast.FunctionDef) and f.name == name)
    env = {'DIAG': logging.getLogger('test_registered_editor')}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<app.py>', 'exec'), env)
    return env[name]


def test_menu_shortcut_uses_existing_host_not_a_second_launcher(monkeypatch):
    import sys
    from external_preview_route import ExternalPreviewTarget
    from registered_editor_preview import RegisteredEditorPreview
    import third_column_host_options
    monkeypatch.setattr(third_column_host_options, 'embedded_editor_enabled', lambda *args: True)
    monkeypatch.setitem(sys.modules, 'registered_editor_preview', SimpleNamespace(
        registered_editor_preview=lambda step, studio_root: RegisteredEditorPreview(
            'external', ExternalPreviewTarget('obsidian', step['launch_target']))))
    monkeypatch.setattr(external_preview_route, 'dedicated_editor_available', lambda x: True)
    monkeypatch.setattr(external_preview_route, 'find_vault_root', lambda x: Path('/vault'))
    called = []
    pane = SimpleNamespace(_workspace_mode='files', isVisible=lambda: True,
        show_external_preview=lambda target: called.append(target) or True)
    stub = SimpleNamespace(expanded_view=pane, view_mode='expanded')
    method = _launcher_method('_try_registered_editor_preview')
    method.__globals__['LAUNCH_HOME'] = Path('/tmp')
    assert method(stub, {'launch_action_type':'Open', 'launch_target':'a.md'}, '')
    assert len(called) == 1
    pane._workspace_mode = 'browser'
    assert not method(stub, {'launch_action_type':'Open', 'launch_target':'a.md'}, '')
    assert len(called) == 1


def test_execute_intercepts_single_step_before_dismiss():
    source = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    segment = source.split('    def execute(self,row,values=None):',1)[1].split('    def next_step(self):',1)[0]
    assert 'expanded_steps.append(step)' in segment
    assert "len(expanded_steps) == 1" in segment
    assert segment.index('_try_registered_editor_preview') < segment.index('self.busy=True')
    assert segment.index('_try_registered_editor_preview') < segment.index('self.dismiss()')


def test_execute_single_registered_shortcut_is_consumed_without_dismiss(monkeypatch, tmp_path):
    """Exercise Launcher.execute's real body, not just helper shape checks."""
    import file_index
    from core import Expander
    from process_runner import should_start_before_dismiss
    from registered_folder_route import embedded_folder_target
    from types import MethodType
    source = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    launcher = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == 'Launcher')
    execute = next(f for f in launcher.body if isinstance(f, ast.FunctionDef) and f.name == 'execute')
    env = {
        'DIAG': logging.getLogger('test_registered_execute'),
        'file_index': file_index,
        'embedded_folder_target': embedded_folder_target,
        'should_start_before_dismiss': should_start_before_dismiss,
        'QTimer': SimpleNamespace(singleShot=lambda _, callback: callback()),
    }
    exec(compile(ast.Module(body=[execute], type_ignores=[]), '<app.py>', 'exec'), env)

    class Stub:
        busy = False
        dismiss_on_outside_click = True
        def __init__(self):
            self.queue = []
            self.previewed = []
            self.dismisses = 0
            self.next_steps = 0
            self._foreground_handoff_pending = False
            self.expander = lambda values=None: Expander({'launch_variables': []}, values=values)
        def open_bookmark_web_view(self, row): return False
        def _resolve_registered_shell_shortcut(self, row): return row
        def _try_registered_editor_preview(self, step, root):
            self.previewed.append(step)
            return True
        def open_registered_step_in_browser(self, step): return False
        def next_step(self): self.next_steps += 1
        def dismiss(self): self.dismisses += 1
        def error(self, exc): raise AssertionError(exc)

    doc = tmp_path / 'note.txt'
    doc.write_text('x', encoding='utf-8')
    row = {'item_id': 'registered', 'title':'Menu file', 'launch_actions':[
        {'launch_action_type':'Open','launch_target':str(doc)}]}
    stub = Stub()
    stub.execute = MethodType(env['execute'], stub)
    stub.execute(row)
    assert len(stub.previewed) == 1
    assert not stub.busy and not stub.queue and stub.dismisses == 0 and stub.next_steps == 0
    # Two commands must not be silently replaced by a preview.
    stub = Stub()
    stub.execute = MethodType(env['execute'], stub)
    stub.execute({'item_id': 'multi', 'title':'Two actions', 'launch_actions':[
        {'launch_action_type':'Open','launch_target':str(doc)},
        {'launch_action_type':'Open','launch_target':'shell:Downloads'}]})
    assert not stub.previewed
    assert stub.next_steps == 1 and stub.dismisses == 1
