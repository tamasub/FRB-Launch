"""Regression: embedded Browser must never end up with zero Web tabs.

Pure Python/AST tests; the real Qt WebEngine surface is checked on Windows.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

from webview_settings import valid_http_url

SRC = Path(__file__).resolve().parents[1] / 'src'
WEB = (SRC / 'launch_web_view.py').read_text(encoding='utf-8')
EXP = (SRC / 'expanded_view.py').read_text(encoding='utf-8')


def extract(source, klass, name):
    tree = ast.parse(source)
    cls = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == klass)
    node = next(item for item in cls.body
                if isinstance(item, ast.FunctionDef) and item.name == name)
    env = {'valid_http_url': valid_http_url}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<browser-default-tab>', 'exec'), env)
    return env[name]


DEFAULT = extract(WEB, 'LaunchWebView', 'default_tab_url')
ENSURE = extract(WEB, 'LaunchWebView', 'ensure_default_tab')
CLOSE = extract(WEB, 'LaunchWebView', 'close_tab')
SHOW = extract(EXP, 'ExpandedLauncherView', '_show_browser_third_column')


class FakeUrl:
    def __init__(self, value): self.value = value
    def toString(self): return self.value


class FakePage:
    def __init__(self, url):
        self._url = FakeUrl(url)
        self.deletion_requested = False
    def url(self): return self._url
    def deleteLater(self): self.deletion_requested = True


class FakeTabWidget:
    def __init__(self, pages=()):
        self.pages = list(pages)
        self.position_updates = 0
    def count(self): return len(self.pages)
    def widget(self, index):
        return self.pages[index] if 0 <= index < self.count() else None
    def removeTab(self, index): self.pages.pop(index)
    def tabBar(self): return NS(_queue_new_tab_position=self.queue_position)
    def queue_position(self): self.position_updates += 1


class FakeBrowser:
    default_tab_url = DEFAULT
    ensure_default_tab = ENSURE
    close_tab = CLOSE

    def __init__(self, urls=(), settings=None):
        self.web_settings = settings or {}
        self.tabs = FakeTabWidget([FakePage(url) for url in urls])
        self.opened = []
        self.address = NS(setText=lambda value: setattr(self, 'address_value', value))
        self.update_url_favorite_button = lambda: None
        self.update_navigation = lambda: None
    def current_view(self): return self.tabs.widget(0)
    def add_tab(self, url=None, *, activate=True):
        self.opened.append((url, activate))
        page = FakePage(url)
        self.tabs.pages.append(page)
        return page


def test_no_tabs_creates_google_default():
    browser = FakeBrowser()
    result = browser.ensure_default_tab()
    assert browser.tabs.count() == 1
    assert result.url().toString() == 'https://www.google.com/'
    assert browser.opened == [('https://www.google.com/', True)]


def test_existing_tabs_remain_unmodified_and_are_not_reloaded():
    browser = FakeBrowser(['https://example.org/draft', 'https://example.org/b'])
    original = browser.tabs.pages[:]
    browser.ensure_default_tab()
    assert browser.opened == []
    assert browser.tabs.pages == original


def test_configured_valid_home_and_invalid_home_fallback():
    browser = FakeBrowser(settings={'new_tab_url': 'https://start.example.org/'})
    assert browser.default_tab_url() == 'https://start.example.org/'
    assert FakeBrowser(settings={'new_tab_url': ''}).default_tab_url() == 'https://www.google.com/'
    assert FakeBrowser(settings={'new_tab_url': 'about:blank'}).default_tab_url() == 'https://www.google.com/'


def test_closing_last_tab_restores_home_and_retires_old_page():
    browser = FakeBrowser(['https://example.org/'])
    old = browser.tabs.pages[0]
    browser.close_tab(0)
    assert old.deletion_requested
    assert browser.tabs.count() == 1
    assert browser.opened == [('https://www.google.com/', True)]
    assert browser.tabs.pages[0] is not old


def test_closing_one_of_multiple_tabs_does_not_change_survivor():
    browser = FakeBrowser(['https://example.org/a', 'https://example.org/form'])
    survivor = browser.tabs.pages[1]
    browser.close_tab(0)
    assert browser.tabs.pages == [survivor]
    assert browser.opened == []
    assert not survivor.deletion_requested


def test_closing_invalid_tab_does_not_create_extra_page():
    browser = FakeBrowser(['https://example.org/a'])
    browser.close_tab(-1)
    assert browser.opened == []
    assert browser.tabs.count() == 1


def test_showing_browser_without_requested_url_ensures_default():
    calls = []
    panel = NS(isHidden=lambda: False)
    obj = NS(_workspace_mode='files', studio_preview=None,
             _ensure_web_view=lambda: True,
             web_view=NS(ensure_default_tab=lambda: calls.append('home')),
             browser_preview=panel,
             middle=NS(tree=NS(hasFocus=lambda: False)),
             _queue_third_column_reflow=lambda: calls.append('reflow'))
    assert SHOW(obj) is True
    assert calls == ['home', 'reflow']


def test_direct_url_request_skips_google_until_navigation():
    calls = []
    obj = NS(_workspace_mode='files', studio_preview=None,
             _ensure_web_view=lambda: True,
             web_view=NS(ensure_default_tab=lambda: calls.append('home')),
             browser_preview=NS(isHidden=lambda: False),
             middle=NS(tree=NS(hasFocus=lambda: False)),
             _queue_third_column_reflow=lambda: calls.append('reflow'))
    assert SHOW(obj, ensure_default_tab=False) is True
    assert calls == ['reflow']
    # The URL request itself still navigates through the existing entry point.
    assert 'self.browser_preview.navigate(url, new_tab=new_tab)' in EXP
    assert 'self._show_browser_third_column(ensure_default_tab=False)' in EXP


def test_prewarm_and_workspace_switch_both_fill_empty_tabs():
    assert EXP.count('self.web_view.ensure_default_tab()') >= 3
    assert "self.web_view.add_tab(self.launcher.webview_settings.get(" not in EXP


def test_touched_source_compiles():
    for name in ('launch_web_view.py', 'expanded_view.py'):
        compile((SRC / name).read_text(encoding='utf-8'), name, 'exec')
