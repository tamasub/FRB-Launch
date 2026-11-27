"""Files Exp > Filesリスト: opening a file closes its entire context cascade.

Qt-free tests exercise the real source methods. Windows/Qt GUI still needs a
manual double-click check because PySide6 is not installed in this runner.
"""

import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

APP = Path(__file__).resolve().parents[1] / 'src' / 'app.py'


def source_method(owner, name, scope):
    module = ast.parse(APP.read_text(encoding='utf-8'))
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == owner)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    fake = ast.Module(body=[method], type_ignores=[])
    exec(compile(ast.fix_missing_locations(fake), str(APP), 'exec'), scope)
    return scope[name]


def setup_activate(monkeypatch):
    import menu_lifecycle as ml
    from processing_display import ProcessingDisplay
    from test_menu_lifecycle_processing_20261127 import Application
    events = []
    display = ProcessingDisplay(Application(events), 'wait', 'exclude')
    monkeypatch.setattr(ml, 'processing_display', lambda: display)
    scope = {'Path': Path, 'finish_selection': ml.finish_selection, 'selection_root': ml.selection_root}
    return source_method('RemoteFolderCascade', '_remote_activate_file', scope), events


def test_file_launch_dismisses_only_owned_menus_before_dispatch(tmp_path, monkeypatch):
    from test_menu_lifecycle_processing_20261127 import Menu
    launch, events = setup_activate(monkeypatch)
    filename = tmp_path / 'example.txt'
    filename.write_text('ok', encoding='utf-8')
    root = Menu('root', events); owner = Menu('child', events, parent=root); root.child = owner
    other = Menu('unrelated', events)
    owner.launcher = NS(activate=lambda row: events.append(('activate', row['_browse_file'])))
    launch(owner, {'_browse_file': str(filename)})
    assert events == [('close','child'),('close','root'),('cursor','wait'),('activate',str(filename)),('restore',)]
    assert other.visible


def test_missing_selected_file_closes_and_reports_error(tmp_path, monkeypatch):
    from test_menu_lifecycle_processing_20261127 import Menu
    launch, events = setup_activate(monkeypatch)
    owner = Menu('root', events)
    owner.launcher = NS(activate=Mock(), error=Mock())
    launch(owner, {'_browse_file': str(tmp_path / 'does_not_exist.txt')})
    assert not owner.visible
    owner.launcher.activate.assert_not_called()
    owner.launcher.error.assert_called_once()
    assert events[-1] == ('restore',)


def test_failed_launch_still_dismisses_finished_command(tmp_path, monkeypatch):
    from test_menu_lifecycle_processing_20261127 import Menu
    import pytest
    launch, events = setup_activate(monkeypatch)
    filename = tmp_path / 'bad.txt'
    filename.write_text('ok', encoding='utf-8')
    def fail(row): raise OSError('cannot start')
    owner = Menu('root', events); owner.launcher = NS(activate=fail)
    with pytest.raises(OSError): launch(owner, {'_browse_file': str(filename)})
    assert not owner.visible and events[-1] == ('restore',)


def test_non_scroll_and_scroll_double_click_share_single_launch_method():
    text = APP.read_text(encoding='utf-8')
    module = ast.parse(text)
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef)
               and n.name == 'RemoteFolderCascade')
    methods = {n.name: ast.get_source_segment(text, n) for n in cls.body
               if isinstance(n, ast.FunctionDef)}
    assert "lambda r=dbl: self._remote_activate_file(r)" in methods['mouseReleaseEvent']
    assert "lambda r=row: self._remote_activate_file(r)" in methods['_scroll_double_clicked']
    assert 'finish_selection' in methods['_remote_activate_file']


def test_context_selection_closes_linked_host_but_inline_handoff_retains_it():
    from menu_lifecycle import close_selection
    from test_menu_lifecycle_processing_20261127 import Menu, Action
    events = []
    host = Menu('host', events); context = Menu('context', events)
    context._frb_selection_parent = host
    action = Action(); action.property = lambda _: True
    close_selection(context, action)
    assert not context.visible and host.visible
    context.visible = True
    close_selection(context, Action())
    assert not context.visible and not host.visible
