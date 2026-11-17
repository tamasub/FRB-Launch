"""Regression: Sakura was withdrawn from Files' third-column hosting.

These tests call the real Files-routing method without a Qt window, so an
old embed_sakura=true state cannot silently reintroduce native HWND docking.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace

import external_preview_route
import third_column_host_options

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py'


def _method(name):
    module = ast.parse(SOURCE.read_text(encoding='utf-8'))
    owner = next(item for item in module.body if isinstance(item, ast.ClassDef)
                 and any(isinstance(node, ast.FunctionDef) and node.name == name
                         for node in item.body))
    target = next(item for item in owner.body
                  if isinstance(item, ast.FunctionDef) and item.name == name)
    namespace = {'os': os, 'Path': Path}
    exec(compile(ast.Module(body=[target], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace[name]


def test_txt_and_ini_always_use_external_sakura_even_with_old_embed_flag(monkeypatch, tmp_path):
    exe = tmp_path / 'sakura.exe'
    exe.write_text('test', encoding='utf-8')
    monkeypatch.setattr(external_preview_route, 'find_sakura_executable', lambda: str(exe))
    # Simulate an existing user state.ini with embed_sakura=true.
    monkeypatch.setattr(third_column_host_options, 'embedded_editor_enabled',
                        lambda home, app: True)
    launched = []
    monkeypatch.setattr(external_preview_route, 'launch_external_standalone',
                        lambda target: launched.append(target))
    view = SimpleNamespace(
        _workspace_mode='files',
        launcher=SimpleNamespace(dismiss_on_outside_click=False,
                                 error=lambda reason: (_ for _ in ()).throw(AssertionError(reason))),
        show_external_preview=lambda target: (_ for _ in ()).throw(
            AssertionError('Sakura must never be embedded')),
    )
    handler = _method('preview_bookmark_from_list')
    for suffix in ('.txt', '.ini'):
        file = tmp_path / ('test' + suffix)
        file.write_text('test', encoding='utf-8')
        assert handler(view, {'_browse_file': str(file)}) is True
    assert [target.app for target in launched] == ['sakura', 'sakura']
    assert [Path(target.path).suffix for target in launched] == ['.txt', '.ini']


def test_sakura_preview_api_fails_closed_before_creating_native_host():
    target = SimpleNamespace(app='sakura', path='C:/temp/sample.txt')
    view = SimpleNamespace(studio_preview=None,
                           _ensure_studio_preview=lambda: (_ for _ in ()).throw(
                               AssertionError('Native pane must not be created')))
    assert _method('show_external_preview')(view, target) is False


def test_obsidian_and_studio_embedding_configuration_is_unchanged():
    source = SOURCE.read_text(encoding='utf-8')
    route = source.split('def preview_bookmark_from_list(', 1)[1].split('def show_browser_preview(', 1)[0]
    assert "external.app != 'sakura' and embedded_editor_enabled(" in route
    assert "if external.app != 'obsidian' or find_vault_root(external.path) is not None:" in route
    assert "'studio')):" in route
    assert "return self.show_studio_preview(target)" in route
