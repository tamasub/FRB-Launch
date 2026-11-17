"""Regression: Launch-authored URL double clicks use the Files Browser Preview."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))
from launch_virtual_tree import virtual_execution_row, virtual_list_rows, virtual_launch_pages
from webview_routes import bookmark_web_url


def method(filename, cls, name, namespace=None):
    tree = ast.parse((SRC / filename).read_text(encoding='utf-8'))
    owner = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == cls)
    fn = next(f for f in owner.body if isinstance(f, ast.FunctionDef) and f.name == name)
    ns = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<authored-preview-contract>', 'exec'), ns)
    return ns[name]


def item(item_id='url-1', target='https://zenn.dev/frb_tamasub', *, enabled=True,
         kind='command', actions=None):
    return {'page_id': 'work', 'item_id': item_id, 'parent_item_id': 'root',
            'title': 'Zenn', 'enabled': enabled, 'item_kind': kind,
            'launch_actions': actions if actions is not None else [
                {'launch_action_type': 'Open', 'launch_target': target}]}


def fixture(row=None):
    root = {'page_id': 'work', 'item_id': 'root', 'parent_item_id': '',
            'title': 'Favorites', 'enabled': True, 'item_kind': 'category'}
    authored = [root, row or item()]
    pages = [{'page_id': 'work', 'title': 'My Work', 'enabled': True}]
    tree = virtual_launch_pages(pages, authored)
    directory = next(c for c in tree[0]['children'] if c['item_id'] == 'root')
    projection = virtual_list_rows(directory)
    return authored, projection[0]


def make_launcher(authored, *, mode='embedded', workspace='files', visible=True):
    urls = []
    view = NS(isVisible=lambda: visible, _workspace_mode=workspace,
              show_browser_preview=lambda url: urls.append(url) or True)
    launch = NS(authored_items=authored, data={'items': authored},
                webview_settings={'mode': mode}, expanded_view=view)
    return launch, urls


def app_preview():
    return method('app.py', 'Launcher', 'preview_authored_launch_url', {
        'virtual_execution_row': virtual_execution_row,
        'bookmark_web_url': bookmark_web_url})


def list_preview():
    return method('expanded_view.py', 'ExpandedLauncherView',
                  'preview_bookmark_from_list')


def test_authored_url_projected_in_list_opens_preview_not_browser_workspace():
    authored, displayed = fixture()
    assert displayed['item_kind'] == 'virtual_launch_file'
    assert displayed['_launch_virtual_node']['runtime_catalog'] == ''
    launch, urls = make_launcher(authored)
    view = NS(_workspace_mode='files', launcher=launch)
    # Exercise the actual Files List route through the Launcher resolver.
    launch.preview_authored_launch_url = lambda row: app_preview()(launch, row)
    assert list_preview()(view, displayed)
    assert urls == ['https://zenn.dev/frb_tamasub']
    assert launch.expanded_view._workspace_mode == 'files'


def test_old_visual_url_is_not_navigation_authority_after_edits():
    authored, displayed = fixture()
    old = displayed['_launch_virtual_node']['row']
    launch, urls = make_launcher([authored[0], item(target='https://example.org/new')])
    assert app_preview()(launch, old)
    assert urls == ['https://example.org/new']
    launch.authored_items = [authored[0]]  # Deleted after List rendered.
    assert not app_preview()(launch, old)
    assert urls == ['https://example.org/new']
    launch.authored_items = [authored[0], item(enabled=False)]
    assert not app_preview()(launch, old)


def test_no_preview_for_non_urls_or_compound_actions():
    row = item()
    bad_cases = [
        item(target='file:///C:/readme.html'),
        item(target='javascript:alert(1)'),
        item(target='https://bad url'),
        item(actions=[{'launch_action_type': 'Run', 'launch_target': 'https://example.org'}]),
        item(actions=[{'launch_action_type': 'Open', 'launch_target': 'https://example.org'},
                      {'launch_action_type': 'Send', 'launch_text': 'surprise'}]),
        item(kind='category'),
        item(target='not-a-url'),
    ]
    for invalid in bad_cases:
        launch, urls = make_launcher([invalid])
        assert not app_preview()(launch, row), invalid
        assert urls == []


def test_dont_preview_unsafe_sources_or_wrong_workspace():
    authored, displayed = fixture()
    launch, urls = make_launcher(authored)
    assert not app_preview()(launch, {**authored[1], '_installed_app': True})
    assert not app_preview()(launch, {**authored[1], '_browser_bookmark': True})
    for mode, workspace, visible in [('external', 'files', True),
                                     ('embedded', 'browser', True),
                                     ('embedded', 'files', False)]:
        other, seen = make_launcher(authored, mode=mode, workspace=workspace, visible=visible)
        assert not app_preview()(other, authored[1])
        assert seen == []
    assert not list_preview()(NS(_workspace_mode='files', launcher=launch),
                              {'_launch_virtual_node': {
                                  'kind': 'file', 'runtime_catalog': 'installed_apps',
                                  'row': authored[1]}})
    assert urls == []


def test_enter_and_other_double_click_paths_not_changed():
    expanded = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    assert "self.launcher.activate_virtual_launch_item(virtual.get('row'))" in expanded
    assert 'self.middle.tree.bookmark_preview_double_click = self.preview_bookmark_from_list' in expanded
    assert 'if not view.preview_bookmark_from_list(row):' in app
    assert 'if catalog:' in expanded  # Runtime apps don't get URL preview.
    assert "return bool(self.launcher.preview_authored_launch_url(virtual.get('row')))" in expanded
