"""Behavior/contract checks for Browser tab -> third-column full workspace.

Qt is unavailable on this Linux runner. Win11 visual verification is separate.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

from third_column_maximize import maximize_sizes, restore_sizes

ROOT = Path(__file__).resolve().parents[1]
EXPANDED = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
BROWSER = (ROOT / 'src/browser_preview_panel.py').read_text(encoding='utf-8')
STUDIO = (ROOT / 'src/studio_preview_panel.py').read_text(encoding='utf-8')
APP = (ROOT / 'src/app.py').read_text(encoding='utf-8')


def method(name):
    cls = next(x for x in ast.parse(EXPANDED).body
               if isinstance(x, ast.ClassDef) and x.name == 'ExpandedLauncherView')
    fn = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name)
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<browser-third-column>', 'exec'), scope)
    return scope[name]


def test_full_web_widget_not_separate_preview_webengine():
    assert 'from launch_web_view import LaunchWebView' in BROWSER
    assert 'self.web_view = LaunchWebView(self, settings=settings)' in BROWSER
    assert 'self.web_view.open_launch_url(url, new_tab=new_tab)' in BROWSER
    assert 'self.web_view.bookmark_strip.hide()' in BROWSER
    assert 'self.files_splitter.addWidget(self.browser_preview)' in EXPANDED
    assert 'self.web_view = panel.web_view' in EXPANDED
    assert 'QWebEngineView(self)' not in BROWSER
    assert "self.view.setUrl(QUrl('about:blank'))" not in BROWSER


def test_no_workspace_strip_and_left_breadcrumb_is_preserved():
    assert 'self.toolbar_scroller.hide()' in EXPANDED
    assert 'group_layout.addWidget(self.shared_header)' in EXPANDED
    assert 'group_layout.addWidget(self.files_splitter, 1)' in EXPANDED
    assert "self.files_content_stack.setCurrentWidget(self.web_view)" not in EXPANDED
    assert "self._workspace_mode = 'browser'" in EXPANDED  # legacy method remains, but never used
    assert 'return self.show_browser_preview(url, new_tab=new_tab)' in EXPANDED


def test_remote_browser_routes_to_same_optional_column():
    assert 'def switch_workspace(self, mode):' in EXPANDED
    assert 'return self._show_browser_third_column()' in EXPANDED
    assert 'self.browser_preview.navigate(url, new_tab=new_tab)' in EXPANDED


def test_browser_and_studio_have_max_and_close_controls():
    for src in (BROWSER, STUDIO):
        assert 'maximize_requested = Signal()' in src
        assert 'self.maximize_button.clicked.connect(self.maximize_requested.emit)' in src
        assert 'self.maximize_button.setToolTip(' in src
        assert 'self.close_button.clicked.connect(self.close_requested.emit)' in src
    assert 'self.studio_preview.maximize_requested.connect(self.toggle_third_column_maximize)' in EXPANDED
    assert 'panel.maximize_requested.connect(self.toggle_third_column_maximize)' in EXPANDED
    assert 'self._preview_normal_columns' in EXPANDED


def test_geometry_maximize_and_restore():
    assert maximize_sizes([300, 600, 400], 2) == [190, 190, 920]
    assert restore_sizes([190, 190, 920], 2, (300, 600, 400)) == [300, 600, 400]
    assert maximize_sizes([300, 600, 0, 400], 3) == [190, 190, 0, 920]
    assert restore_sizes([190, 190, 0, 920], 3, (300, 600, 400)) == [300, 600, 0, 400]


def test_narrow_window_is_nonnegative_and_no_new_width():
    for total in (0, 80, 200, 390, 590, 900, 5000):
        sizes = [total // 5, total * 2 // 5, total - (total // 5) - (total * 2 // 5)]
        got = maximize_sizes(sizes, 2)
        assert sum(got) == total
        assert all(x >= 0 for x in got)


def test_exp_minimum_for_remote_mode_respected():
    assert maximize_sizes([400, 400, 700], 2, 386, 190) == [386, 190, 924]


def test_one_visible_preview_receives_maximize():
    class Pane:
        def __init__(self, hidden): self.hidden=hidden
        def isHidden(self): return self.hidden
    browser, studio = Pane(False), Pane(True)
    get = method('_visible_third_column')
    assert get(NS(browser_preview=browser, studio_preview=studio)) is browser
    browser.hidden, studio.hidden = True, False
    assert get(NS(browser_preview=browser, studio_preview=studio)) is studio
    studio.hidden = True
    assert get(NS(browser_preview=browser, studio_preview=studio)) is None


def test_no_maximized_preference_persistence():
    save = method('save_splitter_sizes')
    save(NS(_preview_maximized=True))  # no settings access when maximized


def test_web_route_can_preserve_new_tab_intent():
    calls=[]
    assert method('show_web_url')(NS(show_browser_preview=lambda url, **kwargs:
                                    calls.append((url,kwargs)) or True),
                                  'https://example.org',new_tab=True)
    assert calls == [('https://example.org', {'new_tab':True})]


def test_wheel_reflow_delayed_after_geometry_changes():
    assert 'self.files_splitter.handle(1)' in EXPANDED
    assert 'self._queue_third_column_reflow()' in EXPANDED
    assert 'QTimer.singleShot(80, self.queue_rail_wheel_position)' in EXPANDED
    assert 'QTimer.singleShot(160, self.queue_rail_wheel_position)' in EXPANDED


def test_src_modules_compile():
    for name in ('expanded_view.py','browser_preview_panel.py','studio_preview_panel.py',
                 'launch_web_view.py','third_column_maximize.py','app.py'):
        compile((ROOT / 'src' / name).read_text(encoding='utf-8'), name, 'exec')


def test_real_maximize_toggle_round_trip_with_hidden_fourth_slot():
    class Pane:
        def __init__(self): self.max_state = False
        def isHidden(self): return False
        def set_maximized(self, state): self.max_state = state
    class Splitter:
        def __init__(self, pane): self.widths=[300,600,0,400]; self.pane=pane
        def sizes(self): return self.widths[:]
        def indexOf(self, pane): return 3
        def setSizes(self, widths): self.widths=list(widths)
    class View:
        _visible_third_column = method('_visible_third_column')
        _apply_third_column_maximized = method('_apply_third_column_maximized')
        toggle_third_column_maximize = method('toggle_third_column_maximize')
        _sync_preview_maximize_buttons = method('_sync_preview_maximize_buttons')
        def _queue_third_column_reflow(self): self.reflows += 1
    v=View();pane=Pane()
    v.browser_preview=None;v.studio_preview=pane;v.files_splitter=Splitter(pane)
    v.launcher=NS(remote_15_mode=False, files_root_hidden_mode=False,
                  files_exp_embedded_mode=True)
    v.middle=NS(minimumWidth=lambda:190)
    v._preview_normal_columns=None;v._preview_maximized=False;v.reflows=0
    v.toggle_third_column_maximize()
    assert v.files_splitter.sizes() == [190,190,0,920]
    assert v._preview_maximized and pane.max_state
    v.toggle_third_column_maximize()
    assert v.files_splitter.sizes() == [300,600,0,400]
    assert not v._preview_maximized and not pane.max_state
    assert v.reflows == 2


def test_maximize_persists_after_resize_until_user_restores():
    class Pane:
        def isHidden(self): return False
        def set_maximized(self, _state): pass
    class Splitter:
        def __init__(self): self.widths=[300,500,400]
        def sizes(self): return self.widths[:]
        def indexOf(self, _pane): return 2
        def setSizes(self, widths): self.widths=list(widths)
    class View:
        _visible_third_column=method('_visible_third_column')
        _apply_third_column_maximized=method('_apply_third_column_maximized')
        toggle_third_column_maximize=method('toggle_third_column_maximize')
        _sync_preview_maximize_buttons=method('_sync_preview_maximize_buttons')
        _after_maximized_splitter_resize=method('_after_maximized_splitter_resize')
        def _queue_third_column_reflow(self): pass
    v=View();v.browser_preview=Pane();v.studio_preview=None
    v.files_splitter=Splitter()
    v.launcher=NS(remote_15_mode=False, files_root_hidden_mode=False,
                  files_exp_embedded_mode=True)
    v.middle=NS(minimumWidth=lambda:190)
    v._preview_maximized=False;v._preview_normal_columns=None
    v.toggle_third_column_maximize()
    # Qt may resize every splitter section while resizing Launch frame.
    v.files_splitter.widths=[250,235,915]
    v._maximized_resize_pending=True
    v._after_maximized_splitter_resize()
    assert v.files_splitter.sizes() == [190,190,1020]
    v.toggle_third_column_maximize()
    assert sum(v.files_splitter.sizes()) == 1400
    assert not v._preview_maximized
