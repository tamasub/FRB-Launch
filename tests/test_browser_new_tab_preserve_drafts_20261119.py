"""Qt-independent regression for Files List's non-destructive URL opening.

Real QWebEngine interaction and unsaved HTML forms require a Win11 manual run.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

from browser_tab_policy import matching_tab_index, comparable_url, empty_tab

SRC = Path(__file__).resolve().parents[1] / 'src'
WEB_SRC = (SRC / 'launch_web_view.py').read_text(encoding='utf-8')
BROWSER_SRC = (SRC / 'browser_preview_panel.py').read_text(encoding='utf-8')
EXP_SRC = (SRC / 'expanded_view.py').read_text(encoding='utf-8')


def get_method(source, cls, name, inject=None):
    klass = next(n for n in ast.parse(source).body
                 if isinstance(n, ast.ClassDef) and n.name == cls)
    method = next(n for n in klass.body
                  if isinstance(n, ast.FunctionDef) and n.name == name)
    env = dict(inject or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 '<browser-auto-tabs>', 'exec'), env)
    return env[name]


class FakeUrl:
    def __init__(self, url): self.value = url
    def toString(self): return self.value


class FakePage:
    def __init__(self, url): self._url = FakeUrl(url)
    def url(self): return self._url


class FakeTabs:
    def __init__(self, urls):
        self.pages = [FakePage(url) for url in urls]
        self.selected = max(0, len(urls) - 1)
    def count(self): return len(self.pages)
    def widget(self, i): return self.pages[i]
    def setCurrentIndex(self, index): self.selected = index


class FakeWeb:
    open_launch_url = get_method(WEB_SRC, 'LaunchWebView', 'open_launch_url')

    def __init__(self, urls):
        self.tabs = FakeTabs(urls)
        self.opens = []

    def current_view(self):
        return self.tabs.widget(self.tabs.selected) if self.tabs.count() else None

    def show_url(self, url, *, new_tab=False):
        self.opens.append((url, new_tab))
        if new_tab or not self.tabs.count():
            self.tabs.pages.append(FakePage(url))
            self.tabs.selected = self.tabs.count() - 1
        else:
            self.tabs.pages[self.tabs.selected] = FakePage(url)


def test_first_url_uses_first_empty_tab():
    web = FakeWeb([])
    web.open_launch_url('https://example.com/one')
    assert web.opens == [('https://example.com/one', False)]
    assert web.tabs.count() == 1


def test_different_url_opens_new_tab_without_overwrite():
    web = FakeWeb(['https://example.com/one'])
    web.open_launch_url('https://example.com/two')
    assert web.opens == [('https://example.com/two', True)]
    assert web.tabs.pages[0].url().toString() == 'https://example.com/one'


def test_reopen_existing_url_selects_its_tab_without_reloading():
    web = FakeWeb(['https://example.com/one', 'https://example.com/two'])
    web.open_launch_url('https://example.com/one', new_tab=True)
    assert web.tabs.selected == 0
    assert web.opens == []
    web.open_launch_url('https://example.com/two')
    assert web.tabs.selected == 1
    assert web.opens == []


def test_explicit_current_tab_preserved_for_user_choice():
    web = FakeWeb(['https://example.com/one'])
    web.open_launch_url('https://example.com/two', new_tab=False)
    assert web.opens == [('https://example.com/two', False)]
    assert web.tabs.count() == 1


def test_navigated_away_from_previous_url_does_not_overwrite_draft():
    web = FakeWeb(['https://example.com/editor?draft=1'])
    web.open_launch_url('https://example.com/one')
    assert web.opens == [('https://example.com/one', True)]


def test_blank_tab_is_reused_only_in_auto_mode():
    auto = FakeWeb(['about:blank'])
    auto.open_launch_url('https://example.com/a')
    assert auto.opens == [('https://example.com/a', False)]
    explicit_new = FakeWeb(['about:blank'])
    explicit_new.open_launch_url('https://example.com/a', new_tab=True)
    assert explicit_new.opens == [('https://example.com/a', True)]


def test_url_matching_is_conservative_and_root_slash_equivalent():
    assert comparable_url('https://EXAMPLE.COM') == comparable_url('https://example.com/')
    assert matching_tab_index(['https://example.com/a', 'https://example.com/b'],
                              'https://example.com/b') == 1
    assert matching_tab_index(['https://example.com/a?x=1'],
                              'https://example.com/a?x=2') is None
    assert not empty_tab('https://example.com')


def test_browser_panel_routes_url_to_safe_policy():
    method = get_method(BROWSER_SRC, 'BrowserPreviewPanel', 'navigate',
                        {'valid_http_url': lambda url: url.startswith('https://')})
    calls = []
    panel = NS(_url='', web_view=NS(open_launch_url=lambda *a, **kw:
                                   calls.append((a, kw))))
    assert method(panel, 'https://example.com/a')
    assert calls == [(('https://example.com/a',), {'new_tab': None})]
    assert method(panel, 'https://example.com/b', new_tab=False)
    assert calls[-1] == (('https://example.com/b',), {'new_tab': False})
    assert not method(panel, 'javascript:alert(1)')


def test_files_view_implicit_url_requests_use_auto_tab():
    assert 'def show_web_url(self, url, *, new_tab=None)' in EXP_SRC
    assert 'def show_browser_preview(self, url, *, new_tab=None)' in EXP_SRC
    assert 'self.browser_preview.navigate(url, new_tab=new_tab)' in EXP_SRC


def test_source_compiles():
    for name in ('launch_web_view.py','browser_preview_panel.py',
                 'expanded_view.py','studio_preview_panel.py','app.py'):
        compile((SRC/name).read_text(encoding='utf-8'), name, 'exec')
