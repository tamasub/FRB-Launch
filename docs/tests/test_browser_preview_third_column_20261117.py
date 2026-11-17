"""FRB Launch bookmark-only third-column preview (Qt-independent contracts)."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))
from launch_virtual_tree import virtual_bookmark_execution_row
from webview_routes import bookmark_web_url
from webview_settings import valid_http_url
import browser_bookmarks


def method(filename, cls, name, namespace=None):
    tree = ast.parse((SRC / filename).read_text(encoding='utf-8'))
    owner = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == cls)
    fn = next(f for f in owner.body if isinstance(f, ast.FunctionDef) and f.name == name)
    ns = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<preview-contract>', 'exec'), ns)
    return ns[name]


def fixture():
    authored = [{'item_id': 'bookmark-root', 'page_id': 'windows',
                 'parent_item_id': '', 'title': 'Bookmarks', 'item_kind': 'category',
                 'enabled': True, 'launch_source': 'browser_bookmarks'}]
    profiles = [{'directory': 'Default', 'browser_profile': 'Default',
                 'roots': [{'name': 'Favorites', 'children': [
                     {'type': 'url', 'name': 'FRB', 'url': 'https://example.org/a?b=1&c=2'}]}]}]
    runtime = browser_bookmarks.attach({'items': authored}, 'chrome', profiles)['items']
    row = next(r for r in runtime if r.get('_browser_bookmark')
               and r.get('item_kind') == 'command')
    return authored, runtime, row


def test_bookmark_url_double_click_previews_authoritative_bookmark_without_switching():
    authored, runtime, row = fixture()
    results = []
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              show_browser_preview=lambda u: results.append(u) or True)
    launch = NS(webview_settings={'mode': 'embedded'}, expanded_view=view,
                authored_items=authored, data={'items': runtime})
    preview = method('app.py', 'Launcher', 'preview_virtual_bookmark', {
        'virtual_bookmark_execution_row': virtual_bookmark_execution_row,
        'bookmark_web_url': bookmark_web_url})
    assert preview(launch, row)
    assert results == ['https://example.org/a?b=1&c=2']
    # A deleted/stale bookmark ID must not launch an old URL.
    assert not preview(launch, {**row, 'item_id': 'deleted'})
    assert len(results) == 1


def test_external_mode_never_instantiates_qwebengine_preview():
    authored, runtime, row = fixture()
    called = []
    launch = NS(webview_settings={'mode': 'external'}, expanded_view=NS(
        isVisible=lambda: True, _workspace_mode='files',
        show_browser_preview=lambda u: called.append(u) or True),
        authored_items=authored, data={'items': runtime})
    preview = method('app.py', 'Launcher', 'preview_virtual_bookmark', {
        'virtual_bookmark_execution_row': virtual_bookmark_execution_row,
        'bookmark_web_url': bookmark_web_url})
    assert not preview(launch, row)
    assert called == []


def test_only_bookmark_url_virtual_leaf_calls_launcher_preview():
    authored, runtime, row = fixture()
    previews = []
    view = NS(_workspace_mode='files', launcher=NS(
        preview_virtual_bookmark=lambda item: previews.append(item) or True))
    maybe = method('expanded_view.py', 'ExpandedLauncherView',
                   'preview_bookmark_from_list')
    leaf = {'_launch_virtual_node': {'kind': 'file',
           'runtime_catalog': 'browser_bookmarks', 'row': row}}
    assert maybe(view, leaf)
    assert previews == [row]
    assert not maybe(view, {'item_kind': 'command'})
    assert not maybe(view, {'_launch_virtual_node': {'kind': 'folder',
                       'runtime_catalog': 'browser_bookmarks', 'row': row}})
    assert not maybe(view, {'_launch_virtual_node': {'kind': 'file',
                       'runtime_catalog': 'apps', 'row': row}})
    view._workspace_mode = 'browser'
    assert not maybe(view, leaf)
    assert previews == [row]


def test_preview_rejects_non_http_or_invalid_urls():
    assert valid_http_url('https://example.org')
    for value in ('javascript:alert(1)', 'file:///C:/Users/foo',
                  'data:text/html,test', 'https://', 'https://example.org/bad url'):
        assert not valid_http_url(value)


def test_transient_third_column_uses_lazy_webengine_and_preserves_two_column_settings():
    expanded = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    browser = (SRC / 'browser_preview_panel.py').read_text(encoding='utf-8')
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    assert 'self.files_splitter.addWidget(self.middle)' in expanded
    assert 'self.files_splitter.addWidget(self.browser_preview)' in expanded
    assert 'from browser_preview_panel import BrowserPreviewPanel' in expanded
    assert 'self.browser_preview.close_requested.connect(self.close_browser_preview)' in expanded
    assert 'self._browser_preview_base_sizes = sizes[:]' in expanded
    assert 'self.files_splitter.setSizes(sizes)' in expanded
    assert "preview = getattr(self, 'browser_preview', None)" in expanded
    assert 'if preview is not None and not preview.isHidden():' in expanded
    assert 'self.middle.tree.bookmark_preview_double_click' in expanded
    assert 'self._preview_double_release_pending' in expanded
    assert "self.view.setUrl(QUrl('about:blank'))" in browser
    assert "self.view.setUrl(QUrl(url))" in browser
    assert "self.close_button.clicked.connect(self.close_requested.emit)" in browser
    # Files List Remote double click agrees with the physical mouse action.
    assert 'if not view.preview_bookmark_from_list(row):' in app
    # Preview module must not be imported eagerly at app startup.
    assert 'from browser_preview_panel import' not in app
    assert 'from browser_preview_panel import' not in expanded.split('    def show_browser_preview(', 1)[0]


def test_close_restores_files_widths_and_stops_only_preview():
    events = []
    class Panel:
        hidden = False
        def isHidden(self): return self.hidden
        def stop_preview(self): events.append('stop')
        def hide(self): self.hidden=True; events.append('hide')
    panel = Panel()
    view = NS(browser_preview=panel, _browser_preview_base_sizes=[300, 700],
              files_splitter=NS(setSizes=lambda x: events.append(('sizes', x))))
    close = method('expanded_view.py', 'ExpandedLauncherView', 'close_browser_preview')
    close(view)
    assert events == ['stop', 'hide', ('sizes', [300, 700])]
    assert view._browser_preview_base_sizes is None
    close(view)
    assert len(events) == 3


def test_open_preview_reuses_one_panel_and_does_not_switch_workspace(monkeypatch):
    # Exercise the actual method against an in-memory Qt panel stand-in;
    # no GUI display or WebEngine binaries are required on CI/Linux.
    import types
    created = []
    class Signal:
        def connect(self, handler): self.handler = handler
    class Panel:
        def __init__(self, parent, *, settings, profile):
            self.hidden = False
            self.close_requested = Signal()
            self.urls = []
            created.append(self)
        def hide(self): self.hidden = True
        def show(self): self.hidden = False
        def isHidden(self): return self.hidden
        def apply_theme(self, theme): self.theme = theme
        def navigate(self, url): self.urls.append(url); return True
    monkeypatch.setitem(sys.modules, 'browser_preview_panel',
                        types.SimpleNamespace(BrowserPreviewPanel=Panel))
    class Splitter:
        def __init__(self): self.widths = [300, 700]; self.children = []
        def sizes(self): return self.widths[:]
        def addWidget(self, child): self.children.append(child)
        def setSizes(self, sizes): self.widths = list(sizes)
    splitter = Splitter()
    view = NS(_workspace_mode='files', browser_preview=None,
              _browser_preview_base_sizes=None, web_view=None,
              files_splitter=splitter,
              middle=NS(tree=NS(hasFocus=lambda: False)),
              close_browser_preview=lambda: None,
              launcher=NS(webview_settings={'mode': 'embedded',
                                            'default_zoom_percent': 90},
                          color_theme='light', error=lambda message: 1/0))
    show = method('expanded_view.py', 'ExpandedLauncherView', 'show_browser_preview')
    assert show(view, 'https://example.org/one')
    assert len(created) == 1
    assert splitter.widths[0] == 300
    assert len(splitter.widths) == 3
    first_widths = splitter.widths[:]
    assert view._workspace_mode == 'files'
    assert show(view, 'https://example.org/two')
    assert len(created) == 1
    assert splitter.widths == first_widths  # no surprise resizing
    assert created[0].urls == ['https://example.org/one', 'https://example.org/two']
    assert view._browser_preview_base_sizes == [300, 700]
    assert not show(view, 'file:///etc/passwd')
    assert len(created[0].urls) == 2
