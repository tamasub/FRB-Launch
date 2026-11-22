"""Qt-free contracts for Files global search focus, Backspace/HOME and warm focus."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def extract(filename, clsname, funcname, scope=None):
    tree = ast.parse((ROOT / 'src' / filename).read_text(encoding='utf-8'))
    cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == clsname)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == funcname)
    ns = dict(scope or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(ROOT / 'src' / filename), 'exec'), ns)
    return ns[funcname]


def test_settled_global_search_hands_first_down_to_files_list():
    events = []
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              _main_search_active=True,
              _focus_files_keyboard_area=lambda area: events.append(area))
    owner = NS(expanded_view=view, search=NS(text=lambda: '佐藤'),
               selection=None, composing=False)
    fn = extract('app.py', 'Launcher', 'focus_settled_global_search_results', {
        'QApplication': NS(activeModalWidget=lambda: None)})
    assert fn(owner) is True
    assert events == ['list']
    view._main_search_active = False
    assert fn(owner) is False
    view._main_search_active = True
    owner.composing = True
    assert fn(owner) is False
    assert events == ['list']


def test_live_search_render_never_steals_focus_and_respects_ime():
    events = []
    owner = NS(composing=False, render=lambda: events.append('render'),
               focus_settled_global_search_results=lambda: events.append('focus'))
    fn = extract('app.py', 'Launcher', 'render_settled_search')
    fn(owner)
    assert events == ['render']
    owner.composing = True
    owner._live_search_timer = NS(start=lambda delay: events.append(('retry', delay)))
    fn(owner)
    assert events == ['render', ('retry', 235)]


def test_backspace_clears_search_and_leaves_keyboard_on_files_list():
    events = []
    query = NS(text=lambda: '佐藤', clear=lambda: events.append('clear-query'))
    view = NS(_main_search_active=True, _workspace_mode='files',
              isVisible=lambda: True,
              _focus_files_keyboard_area=lambda area: events.append(('focus', area)))
    owner = NS(expanded_view=view, search=query,
               _live_search_timer=NS(stop=lambda: events.append('stop-timer')),
               hide_history_popup=lambda: events.append('hide-history'))
    fn = extract('app.py', 'Launcher', 'clear_global_search_from_list')
    assert fn(owner)
    assert events == ['stop-timer', 'hide-history', 'clear-query', ('focus', 'list')]
    view._main_search_active = False
    assert not fn(owner)


def test_search_list_backspace_only_intercepts_normal_tree_not_editor():
    events = []
    class Widget:
        def window(self): return launcher
    class Tree(Widget):
        def viewport(self): return self
        def state(self): return 'not-editing'
    tree = Tree()
    launcher = NS(clear_global_search_from_list=lambda: events.append('clear') or True)
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              _main_search_active=True, embedded_files_exp=None,
              launcher=launcher, middle=NS(tree=tree),
              _files_keyboard_focus_area=lambda obj: 'list')
    event = NS(type=lambda: 'press', key=lambda: 0x01000003,
               modifiers=lambda: 0, accept=lambda: events.append('accept'))
    qt = NS(Key=NS(Key_Backspace=0x01000003),
            KeyboardModifier=NS(NoModifier=0),
            FocusReason=NS(ShortcutFocusReason=0))
    fn = extract('expanded_view.py', 'ExpandedLauncherView',
                 'keyboard_files_shortcuts', {
                     'QEvent': NS(Type=NS(KeyPress='press')),
                     'QApplication': NS(activeModalWidget=lambda: None),
                     'QWidget': Widget, 'Qt': qt,
                     'QAbstractItemView': NS(State=NS(EditingState='editing')),
                 })
    assert fn(view, tree, event) is True
    assert events == ['clear', 'accept']
    # Editing state excludes the Backspace interception branch, preserving
    # native deletion in the inline filename editor.
    source = (ROOT / 'src' / 'expanded_view.py').read_text(encoding='utf-8')
    assert 'self.middle.tree.state() != QAbstractItemView.State.EditingState' in source


def test_home_clears_main_query_before_collapsing_exp():
    events = []
    panel = NS(reset_to_roots=lambda: events.append('exp-reset'),
               select_first_root_for_home=lambda: ('pc', None),
               isVisible=lambda: True,
               tree=NS(setFocus=lambda reason: events.append('focus-exp')))
    query = NS(text=lambda: '佐藤', clear=lambda: events.append('clear-query'))
    view = NS(isVisible=lambda: True,
              show_files_view=lambda: events.append('files-visible'),
              _embedded_files_exp_roots_ready=True,
              embedded_files_exp=panel)
    win = NS(data=True, pages=[{'page_id': 'work'}],
             expanded_view=view, search=query,
             _live_search_timer=NS(stop=lambda: events.append('stop-timer')),
             hide_history_popup=lambda: events.append('hide-history'),
             files_exp_embedded_mode=True, files_root_hidden_mode=True,
             navigate_files_exp_pc=lambda: events.append('preview-pc') or True,
             remote_focus_area=lambda area: events.append(('focus-area', area)),
             remote_15_mode=False)
    fn = extract('app.py', 'Launcher', 'navigate_home', {
        'Qt': NS(FocusReason=NS(ShortcutFocusReason='shortcut'))})
    fn(win)
    assert events.index('clear-query') < events.index('exp-reset')
    assert events[-2:] == [('focus-area', 'files_exp'), 'focus-exp']


def test_focus_visual_tracks_exact_keyboard_area_not_remote_target():
    calls = []
    class FakeWidget:
        def __init__(self, name):
            self.name, self.props = name, {}
        def property(self, key): return self.props.get(key)
        def setProperty(self, key, value): self.props[key] = value
        def style(self): return self
        def unpolish(self, obj): calls.append(('unpolish', self.name))
        def polish(self, obj): calls.append(('polish', self.name))
        def update(self): pass
        def viewport(self): return self
        def header(self): return headers
    exp_title, exp_tree = FakeWidget('Exp title'), FakeWidget('Exp tree')
    list_title, list_tree = FakeWidget('List title'), FakeWidget('List tree')
    headers = FakeWidget('Header')
    crumb, crumb_edit = FakeWidget('Crumb'), FakeWidget('Crumb edit')
    folder_filter, search = FakeWidget('Filter'), FakeWidget('Global search')
    remote_exp = NS(exp_header=FakeWidget('Remote title'), tree=FakeWidget('Remote tree'))
    view = NS(_workspace_mode='files', isVisible=lambda: True,
              embedded_files_exp=NS(exp_header=exp_title, tree=exp_tree),
              middle=NS(tree=list_tree), files_list_title_box=list_title,
              middle_tree_container=FakeWidget('List container'),
              middle_back_lane=FakeWidget('List lane'),
              middle_search=folder_filter,
              address_bar=NS(surface=crumb, editor=crumb_edit),
              launcher=NS(remote_window=NS(files_exp_panel=remote_exp), search=search))
    fn = extract('expanded_view.py', 'ExpandedLauncherView',
                 'set_files_keyboard_focus_visual')
    fn(view, 'list')
    assert list_title.property('keyboardFocusActive') is True
    assert list_tree.property('keyboardFocusActive') is True
    assert exp_title.property('keyboardFocusActive') is False
    fn(view, 'breadcrumb')
    assert list_title.property('keyboardFocusActive') is False
    assert crumb.property('keyboardFocusActive') is True
    assert folder_filter.property('keyboardFocusActive') is False
    fn(view, 'folder_search')
    assert crumb.property('keyboardFocusActive') is False
    assert folder_filter.property('keyboardFocusActive') is True
    fn(view, 'exp')
    assert exp_title.property('keyboardFocusActive') is True
    assert list_title.property('keyboardFocusActive') is False
    fn(view, None)
    assert exp_title.property('keyboardFocusActive') is False


def test_focus_palette_is_distinct_from_logical_operating_selection():
    view = (ROOT / 'src' / 'expanded_view.py').read_text(encoding='utf-8')
    exp = (ROOT / 'src' / 'remote_files_explorer.py').read_text(encoding='utf-8')
    app = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    assert 'QFrame#filesListTitleBox[keyboardFocusActive="true"]' in view
    assert 'QTreeWidget#expandedTree[keyboardFocusActive="true"]' in view
    assert 'QLineEdit#expandedMiddleSearch[keyboardFocusActive="true"]' in view
    assert 'QFrame#addressBreadcrumbSurface[keyboardFocusActive="true"]' in view
    assert 'QTreeView#filesExpTree[keyboardFocusActive="true"]' in exp
    assert 'QTreeView#filesExpTree[operatingActive="true"]::item:selected' in exp
    assert 'QLineEdit#mainSearchField[keyboardFocusActive="true"]' in app
    assert 'view.set_files_keyboard_focus_visual(area)' in app
