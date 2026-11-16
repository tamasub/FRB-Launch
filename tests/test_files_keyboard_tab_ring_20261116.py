"""Files Tab/Home/Ctrl+I keyboard contracts (Qt-free production-method tests)."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
EXP = (ROOT/'src/expanded_view.py').read_text('utf-8')
APP = (ROOT/'src/app.py').read_text('utf-8')


def load_method(source, cls_name, method, environment):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
    ns = dict(environment)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<Files-keyboard>', 'exec'), ns)
    return ns[method]


class Widget:
    def __init__(self, label='', window=None):
        self.label, self.parent_window, self.focus_count, self.clicks = label, window, 0, 0
        self._viewport = None
    def window(self):
        return self.parent_window
    def setFocus(self, reason):
        self.focus_count += 1
    def isVisible(self):
        return True
    def viewport(self):
        if self._viewport is None:
            self._viewport = Widget(self.label + '.viewport', self.parent_window)
        return self._viewport
    def click(self):
        self.clicks += 1


class Key:
    Key_Tab=1; Key_Backtab=2; Key_Home=3; Key_I=4; Key_Return=5; Key_Enter=6

class Qt:
    Key=Key
    KeyboardModifier=NS(NoModifier=0, ShiftModifier=1, ControlModifier=2)
    FocusReason=NS(TabFocusReason=1, ShortcutFocusReason=2)

class Event:
    def __init__(self, key, mods=0):
        self._key, self._mods, self.accepted = key, mods, False
    def type(self): return 99
    def key(self): return self._key
    def modifiers(self): return self._mods
    def accept(self): self.accepted=True


ENV = dict(QEvent=NS(Type=NS(KeyPress=99)), Qt=Qt, QWidget=Widget,
           QApplication=NS(activeModalWidget=lambda: None))


def scenario():
    calls = []
    launcher = Widget('launcher')
    launcher.search = Widget('global-search', launcher)
    launcher.theme_menu = object()
    launcher.open_theme_menu = lambda: calls.append('settings-menu')
    launcher.open_option_settings = lambda: calls.append('options-dialog')
    launcher.navigate_home = lambda: calls.append('home')
    launcher.set_files_operating_target = lambda value: calls.append(('area', value))
    launcher.stop_auto_shuriken_on_list_click = lambda: calls.append('settle')
    view = NS(_workspace_mode='files', launcher=launcher,
              isVisible=lambda: True,
              middle_search_history_menu=Widget('folder-search-menu', launcher),
              favorite_popup=NS(isVisible=lambda: False),
              hide_favorite_popup=lambda: None)
    exp_tree = Widget('exp', launcher)
    exp_tree.currentIndex = lambda: NS(isValid=lambda: True)
    view.embedded_files_exp = NS(tree=exp_tree, isVisible=lambda: True)
    list_tree = Widget('list', launcher)
    view.middle = NS(tree=list_tree)
    view.middle_search = Widget('local-search', launcher)
    view.middle_search_history_button = Widget('local-search-history', launcher)
    view.middle_search_history_menu.hide = lambda: None
    view.favorite_dropdown = Widget('breadcrumb', launcher)
    view.favorite_choices = Widget('breadcrumb-pop', launcher)
    view.address_bar = NS(editor=Widget('breadcrumb-editor', launcher))
    view.browser_mode_tab = Widget('browser', launcher)
    view.files_mode_tab = Widget('files-tab', launcher)
    view.root_buttons = [Widget('page-root', launcher)]
    view.workspace_page_buttons = [Widget('page-button', launcher)]
    launcher.history_choices = Widget('history-pop', launcher)
    launcher.history_filter = Widget('history-filter', launcher)
    launcher.history_popup = NS(isVisible=lambda: False)
    view.focus_panel = lambda panel: panel.tree.setFocus(Qt.FocusReason.TabFocusReason)
    view._files_keyboard_focus_area = lambda obj: focus_area(view, obj)
    view._focus_files_keyboard_area = lambda area: focus_to(view, area)
    view.keyboard_files_shortcuts = lambda obj,ev: shortcut(view,obj,ev)
    return view, calls, [exp_tree, list_tree, view.middle_search,
                         view.favorite_dropdown, launcher.search, view.browser_mode_tab]

focus_area = load_method(EXP, 'ExpandedLauncherView', '_files_keyboard_focus_area', ENV)
focus_to = load_method(EXP, 'ExpandedLauncherView', '_focus_files_keyboard_area', ENV)
shortcut = load_method(EXP, 'ExpandedLauncherView', 'keyboard_files_shortcuts', ENV)


def test_six_stop_tab_ring_skips_files_tab_and_shift_tab_reverses():
    view, calls, widgets = scenario()
    for index, source in enumerate(widgets):
        ev = Event(Key.Key_Tab)
        assert view.keyboard_files_shortcuts(source, ev) is True
        assert ev.accepted
        assert widgets[(index+1)%6].focus_count == 1
    assert calls.count('settle') == 1
    assert widgets[0].focus_count == 1, 'Browser -> Exp loops'
    assert view._files_keyboard_focus_area(view.files_mode_tab) == 'main_search'
    assert view._files_keyboard_focus_area(view.root_buttons[0]) == 'browser'
    ev = Event(Key.Key_Backtab)
    assert view.keyboard_files_shortcuts(widgets[0], ev)
    assert widgets[-1].focus_count == 2
    ev = Event(Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert view.keyboard_files_shortcuts(widgets[1], ev)
    assert widgets[0].focus_count == 2


def test_tab_can_leave_each_open_history_popup():
    view, calls, widgets = scenario()
    assert view._files_keyboard_focus_area(view.middle_search_history_menu) == 'folder_search'
    # Other popups expose their tree/viewport, not the opener.
    assert view._files_keyboard_focus_area(view.favorite_choices.viewport()) == 'breadcrumb'
    assert view._files_keyboard_focus_area(view.launcher.history_choices.viewport()) == 'main_search'


def test_folder_search_focus_keeps_editable_field_and_down_handler():
    view, calls, widgets = scenario()
    view._focus_files_keyboard_area('folder_search')
    assert view.middle_search.focus_count == 1
    assert view.middle_search_history_button.focus_count == 0
    code = load_method(EXP, 'ExpandedLauncherView', 'handle_middle_search_history_key',
                       dict(QEvent=NS(Type=NS(KeyPress=99)), Qt=NS(
                           KeyboardModifier=NS(NoModifier=0), Key=NS(Key_Down=1, Key_Up=2,
                           Key_Return=3, Key_Enter=4, Key_Escape=5),
                           FocusReason=NS(ShortcutFocusReason=1))))
    menu = NS(visible=False, isVisible=lambda:menu.visible, setActiveAction=lambda a:None)
    view.middle_search_history_menu = menu
    view.toggle_middle_search_history_menu = lambda:setattr(menu, 'visible', True)
    view._middle_search_history_keyword_actions = []
    ev = NS(type=lambda:99, modifiers=lambda:0, key=lambda:1, accept=lambda:None)
    assert code(view, view.middle_search, ev) and menu.visible


def test_home_and_ctrl_i_show_the_gear_menu_from_exp_list_search():
    view, calls, widgets = scenario()
    for widget in widgets:
        assert view.keyboard_files_shortcuts(widget, Event(Key.Key_Home))
        assert view.keyboard_files_shortcuts(widget,
            Event(Key.Key_I, Qt.KeyboardModifier.ControlModifier))
    assert calls.count('home') == len(widgets)
    assert calls.count('settle') == len(widgets)
    assert calls.count('settings-menu') == len(widgets)
    assert 'options-dialog' not in calls
    assert not view.keyboard_files_shortcuts(widgets[2], Event(Key.Key_I)), 'bare I is editable'


def test_browser_enter_clicks_real_tab_and_legacy_views_untouched():
    view, calls, widgets = scenario()
    browser = widgets[-1]
    assert view.keyboard_files_shortcuts(browser, Event(Key.Key_Return))
    assert browser.clicks == 1
    view._workspace_mode = 'browser'
    assert not view.keyboard_files_shortcuts(widgets[0], Event(Key.Key_Tab))


def test_app_wires_space_to_existing_shuriken_landing_and_home_to_exp_focus():
    shuriken = load_method(APP, 'Launcher', 'shuriken_keyboard_list_key',
                          {'Qt':NS(Key=NS(Key_PageUp=1, Key_PageDown=2, Key_Up=3,
                               Key_Down=4, Key_Escape=5, Key_Space=6)),
                           'shuriken_trace': lambda *a,**kw: None})
    land = []
    pad = NS(_flight=object(), _flight_target=None, _settle=lambda:land.append('land'))
    tree = object();pad._flight_target = tree
    pane = NS(tree=tree)
    view = NS(current_directory=lambda:'C:/x', _virtual_directory_node=None)
    launcher = NS(expanded_view=view, _shuriken_keyboard_gate=NS(reset=lambda:None),
                  remote_window=NS(scroll_pad=pad))
    assert shuriken(launcher, 6, None, pane) is True
    assert land == ['land']
    # HOME calls existing semantic handler + focuses actual Exp tree.
    assert 'panel.tree.setFocus(Qt.FocusReason.ShortcutFocusReason)' in APP
    assert 'self.nav_home_button.clicked.connect(self.navigate_home)' in APP
    assert 'self.keyboard_files_shortcuts(obj, event)' in EXP


def test_home_handler_finishes_with_actual_exp_tree_focus_not_just_coloring():
    from test_home_files_exp_first_row_contract_20261102 import fake_launcher_home
    method = load_method(APP, 'Launcher', 'navigate_home', {'Qt': Qt})
    launcher, calls = fake_launcher_home()
    focus = []
    launcher.expanded_view.embedded_files_exp.tree = NS(
        setFocus=lambda reason: focus.append(reason))
    method(launcher)
    assert focus == [Qt.FocusReason.ShortcutFocusReason]
    assert calls[:4] == ['files-visible', 'exp-collapsed', 'exp-selected', 'preview-pc']
    assert calls[-1] == ('focus', 'files_exp')


def test_breadcrumb_tab_stop_is_enabled_even_without_saved_folders():
    assert 'self.favorite_dropdown.setFocusPolicy(Qt.FocusPolicy.StrongFocus)' in EXP
    assert 'self.favorite_dropdown.setEnabled(True)' in EXP
