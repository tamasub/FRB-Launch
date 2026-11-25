"""Browser option: ViewDef, runtime mode, and actual external URL dispatch.

Qt/Windows-independent contracts; live Generic Editor composition is checked
on the Windows installation with the sibling Studio runtime.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from webview_settings import read_webview_settings
from registered_url_route import registered_embedded_url
from webview_routes import bookmark_web_url

ROOT = Path(__file__).resolve().parents[1]


def method(file, cls, name, **scope):
    tree = ast.parse((ROOT / 'src' / file).read_text(encoding='utf-8'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), file, 'exec'), scope)
    return scope[name]


def test_viewdef_exposes_existing_mode_and_hides_only_embedded_fields():
    path = ROOT / 'defs/launch/options/webview_settings_view_def_v0_1.json'
    fields = json.loads(path.read_text(encoding='utf-8'))['views'][0]['sections'][0]['fields']
    assert [f['field'] for f in fields] == ['mode', 'remember_login', 'new_tab_url']
    mode = fields[0]
    assert mode['type'] == 'select' and mode['edit']['visible']
    assert [o['value'] for o in mode['options']] == ['embedded', 'external']
    assert 'visibleWhen' not in mode
    assert all(f['visibleWhen'] == {'field': 'mode', 'equals': 'embedded'} for f in fields[1:])
    assert '再起動' in mode['caption']


def test_settings_preserve_old_values_and_default(tmp_path):
    path = tmp_path / 'webview_settings.json'
    assert read_webview_settings(path)['mode'] == 'embedded'
    data = {'remember_login': False, 'new_tab_url': 'https://example.org/custom'}
    for mode in (None, 'external', 'embedded'):
        raw = dict(data)
        if mode is not None:
            raw['mode'] = mode
        path.write_text(json.dumps(raw), encoding='utf-8')
        before = path.read_bytes()
        result = read_webview_settings(path)
        assert result['mode'] == (mode or 'embedded')
        assert all(result[k] == v for k, v in data.items())
        assert path.read_bytes() == before


@pytest.mark.parametrize('name,args', [('_ensure_web_view', ()),
    ('prewarm_browser', ()), ('switch_workspace', ('browser',)),
    ('show_web_url', ('https://example.org/',)),
    ('show_browser_preview', ('https://example.org/',)),
    ('_show_browser_third_column', ())])
def test_external_mode_refuses_before_widget_creation_or_editor_release(name, args):
    view = NS(launcher=NS(webview_settings={'mode': 'external'}), _workspace_mode='files',
              _ensure_web_view=Mock(side_effect=AssertionError('must not construct')),
              show_browser_preview=Mock(side_effect=AssertionError('must not preview')),
              studio_preview=Mock(side_effect=AssertionError('must not release editor')))
    result = method('expanded_view.py', 'ExpandedLauncherView', name)(view, *args)
    assert not result
    view._ensure_web_view.assert_not_called()
    view.show_browser_preview.assert_not_called()


def test_external_startup_skips_prewarm():
    launch = NS(webview_settings={'mode': 'external'}, expanded_view=NS(prewarm_browser=Mock()))
    method('app.py', 'Launcher', 'prepare_browser_before_first_show')(launch)
    launch.expanded_view.prewarm_browser.assert_not_called()


def test_external_url_routes_decline_without_touching_search_or_browser():
    url = 'https://example.org/a?x=1%20b'
    step = {'launch_action_type': 'Open', 'launch_target': url}
    row = {'item_kind': 'command', 'launch_actions': [step]}
    launch = NS(webview_settings={'mode': 'external'}, selection=None,
                search=NS(text=lambda: 'abc', clear=Mock()), expanded_view=Mock())
    env = {'registered_embedded_url': registered_embedded_url, 'bookmark_web_url': bookmark_web_url}
    assert not method('app.py', 'Launcher', 'open_registered_step_in_browser', **env)(launch, step)
    assert not method('app.py', 'Launcher', 'open_search_url_in_browser', **env)(launch, row)
    assert not method('app.py', 'Launcher', 'open_bookmark_web_view', **env)(launch, row)
    launch.search.clear.assert_not_called()
    assert not launch.expanded_view.mock_calls


def test_unqualified_url_uses_os_association_and_explicit_profiles_are_retained():
    os_mock = NS(startfile=Mock())
    win = NS(IS_WINDOWS=True, open_chrome=Mock(), open_browser=Mock())
    open_target = method('app.py', 'Launcher', 'open_target', os=os_mock, windows=win, Path=Path)
    url = 'https://example.org/a?x=1%20b'
    open_target(NS(), url)
    os_mock.startfile.assert_called_once_with(url)
    win.open_chrome.assert_not_called()
    win.open_browser.assert_not_called()
    open_target(NS(), url, 'edge', 'Profile 2')
    win.open_browser.assert_called_once_with(url, 'edge', 'Profile 2')
    open_target(NS(), url, 'chrome')
    win.open_chrome.assert_called_once_with(url)
    assert os_mock.startfile.call_count == 1


def test_file_index_compose_failure_does_not_disable_browser_user_setting(tmp_path):
    # Execute just the initialization block, with the real configuration reader.
    app = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    tree = ast.parse(app)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Launcher')
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
    start = next(i for i,n in enumerate(init.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='option_errors' for t in n.targets))
    block = init.body[start:start+4]
    assert isinstance(block[-1], ast.If)
    effective = tmp_path / 'effective.json'
    effective.write_text('{"mode":"external"}', encoding='utf-8')
    def compose(home, state, option):
        if option == 'file_index':
            raise RuntimeError('index options failed')
        return effective
    timer = NS(singleShot=Mock())
    launch = NS()
    exec(compile(ast.Module(body=block, type_ignores=[]), 'option_init', 'exec'),
         dict(self=launch, LAUNCH_HOME=tmp_path, STATE=tmp_path,
              effective_options_path=compose, read_webview_settings=read_webview_settings, QTimer=timer))
    assert launch.webview_settings['mode'] == 'external'
    assert launch.file_index_options_path == tmp_path / 'config/file_index_options.json'
    timer.singleShot.assert_called_once()
