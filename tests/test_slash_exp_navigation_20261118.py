"""Portable behavioural tests for the 2026-11-18 / Exp menu prototype.

Stub only Qt's rendering/focus surface; run the ACTUAL production keyPressEvent
and model traversal logic without needing a desktop Qt installation on CI.
The Windows Qt GUI acceptance test remains manual.
"""
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'src' / 'slash_exp_navigation.py'


class Signal:
    def __init__(self):
        self.callbacks = []
    def connect(self, callback):
        self.callbacks.append(callback)
    def emit(self, *args):
        for callback in tuple(self.callbacks):
            callback(*args)
    def disconnect(self, callback):
        self.callbacks.remove(callback)


class FakeIcon:
    def isNull(self):
        return True


class FakeAction:
    def __init__(self, child=None):
        self.child = child
        self.enabled = True
        self.triggered = Signal()
        self.caption = ''
    def text(self):
        return self.caption
    def trigger(self):
        self.triggered.emit()
    def icon(self):
        return getattr(self, '_icon', FakeIcon())
    def isSeparator(self):
        return getattr(self, 'separator', False)
    def menu(self):
        return self.child
    def setMenu(self, value):
        self.child = value
    def setText(self, value):
        self.caption = value
    def setIcon(self, value):
        self._icon = value
    def setToolTip(self, value):
        self.tooltip = value
    def toolTip(self):
        return getattr(self, 'tooltip', '')
    def setEnabled(self, value):
        self.enabled = value
    def setVisible(self, value):
        self.visible = value
    def isVisible(self):
        return getattr(self, 'visible', True)
    def isEnabled(self):
        return self.enabled
    def setIconVisibleInMenu(self, value):
        pass


class FakeRect:
    def isValid(self):
        return True
    def right(self):
        return 210
    def center(self):
        return SimpleNamespace(y=lambda: 5)
    def top(self):
        return 0


class FakeQMenu:
    def __init__(self, parent=None):
        self.parent = parent
        self.aboutToShow = Signal()
        self.aboutToHide = Signal()
        self.triggered = Signal()
        self.entries = []
        self.current = None
        self.visible = False
    def setObjectName(self, *args):
        pass
    def setAttribute(self, *args):
        pass
    def setStyleSheet(self, *args):
        pass
    def styleSheet(self):
        return ''
    def setMaximumHeight(self, height):
        self.maximum_height = height
    def setFixedWidth(self, width):
        self.fixed_width = width
    def fontMetrics(self):
        def advance(title):
            return sum(11 if ord(char) >= 0x3000 else 7 for char in str(title))
        def elide(name, _mode, pixels):
            if advance(name) <= pixels:
                return name
            for i in range(len(name), 0, -1):
                if advance(name[:i] + '…') <= pixels:
                    return name[:i] + '…'
            return '…'
        return SimpleNamespace(horizontalAdvance=advance, elidedText=elide)
    def addSeparator(self):
        action = FakeAction()
        action.separator = True
        self.entries.append(action)
        return action
    def addAction(self, *args):
        action = FakeAction()
        action.caption = str(args[0]) if args else ''
        self.entries.append(action)
        return action
    def setToolTipsVisible(self, *args):
        pass
    def setMinimumWidth(self, *args):
        pass
    def setMaximumWidth(self, *args):
        pass
    def addMenu(self, child):
        action = FakeAction(child)
        self.entries.append(action)
        return action
    def setActiveAction(self, action):
        self.current = action
    def removeAction(self, action):
        self.entries.remove(action)
    def activeAction(self):
        return self.current
    def actionGeometry(self, action):
        return FakeRect()
    def width(self):
        return getattr(self, 'fixed_width', 240)
    def height(self):
        return 350
    def isVisible(self):
        return self.visible
    def move(self, *args):
        self.moved = args
        self._position = args[0]
    def pos(self):
        return getattr(self, '_position', (0, 0))
    def moveEvent(self, event):
        pass
    def screen(self):
        return None
    def mapToGlobal(self, point):
        return point
    def actionAt(self, point):
        return self.current
    def popup(self, point):
        self.popup_point = point
        self._position = point
        self.visible = True
        self.aboutToShow.emit()
    def setFocus(self, *args):
        pass
    def setWindowFlags(self, *args):
        self.window_flags = args[0]
    def activateWindow(self):
        self.activated = True
    def setWindowFlag(self, *args):
        pass
    def setParent(self, parent):
        self.parent = parent
    def parentWidget(self):
        return self.parent
    def hide(self):
        self.visible = False
    def close(self):
        self.visible = False
        self.aboutToHide.emit()
    def deleteLater(self):
        pass
    def actions(self):
        return list(self.entries)
    def eventFilter(self, obj, event):
        return False
    def keyPressEvent(self, event):
        # Native QMenu's Right on a submenu QAction opens its owning child.
        if event.key() == 103 and self.current and self.current.menu():
            child = self.current.menu()
            child.popup((self.width(), 0))
            if child.entries:
                child.setActiveAction(child.entries[0])
            return
        raise AssertionError('Unexpected key forwarded to native QMenu')


class Item:
    def __init__(self, name, metadata, *children):
        self.name = name
        self.meta = metadata
        self.children = list(children)
        self.loaded = False
    def data(self, role):
        if role == 101:
            return self.meta
        if role == 102:
            return self.loaded
    def child(self, index):
        return self.children[index]
    def rowCount(self):
        return len(self.children)
    def index(self):
        return self
    def isEnabled(self):
        return True
    def text(self):
        return self.name
    def icon(self):
        return 'folder-icon'
    def toolTip(self):
        return self.name


class Panel:
    def __init__(self, items):
        self.root = Item('root', None, *items)
        self.model = SimpleNamespace(invisibleRootItem=lambda: self.root)
        self.loaded = []
    def _expand_index(self, item):
        self.loaded.append(item.name)
        item.loaded = True


class Event:
    def __init__(self, key, *, text='', modifiers=0):
        self._key = key
        self._text = text
        self._modifiers = modifiers
        self.accepted = False
    def key(self):
        return self._key
    def modifiers(self):
        return self._modifiers
    def text(self):
        return self._text
    def accept(self):
        self.accepted = True
    def isAccepted(self):
        return self.accepted


@pytest.fixture
def nav(monkeypatch):
    key = SimpleNamespace(Key_Slash=47, Key_Up=100, Key_Down=101,
                          Key_Left=102, Key_Right=103, Key_Return=104,
                          Key_Enter=105, Key_Escape=106, Key_Backspace=107)
    qt = SimpleNamespace(TextElideMode=SimpleNamespace(ElideRight=1),
                         MouseButton=SimpleNamespace(LeftButton=1),
                         ItemDataRole=SimpleNamespace(UserRole=100),
                         WidgetAttribute=SimpleNamespace(WA_InputMethodEnabled=0,
                                                          WA_TranslucentBackground=1),
                         WindowType=SimpleNamespace(Popup=2, FramelessWindowHint=4,
                             Tool=8, WindowStaysOnTopHint=16),
                         ApplicationState=SimpleNamespace(ApplicationInactive=1,
                             ApplicationActive=2),
                         KeyboardModifier=SimpleNamespace(NoModifier=0, ShiftModifier=1,
                            ControlModifier=2, AltModifier=4),
                         FocusReason=SimpleNamespace(OtherFocusReason=0),
                         FocusPolicy=SimpleNamespace(StrongFocus=1),
                         ScrollBarPolicy=SimpleNamespace(ScrollBarAlwaysOff=0,
                                                        ScrollBarAsNeeded=1),
                         GlobalColor=SimpleNamespace(transparent=0),
                         AlignmentFlag=SimpleNamespace(AlignCenter=1,
                             AlignRight=2, AlignVCenter=4), Key=key)
    qtcore = ModuleType('PySide6.QtCore')
    class FakePoint:
        def __init__(self, x, y): self._x, self._y = x, y
        def x(self): return self._x
        def y(self): return self._y
        def __eq__(self, other):
            return (hasattr(other, 'x') and hasattr(other, 'y') and
                    self._x == other.x() and self._y == other.y())
    qtcore.QPoint = FakePoint
    class FakeQObject:
        def __init__(self, parent=None): self._parent = parent
    qtcore.QObject = FakeQObject
    qtcore.QRect = lambda *args: tuple(args)
    qtcore.QSize = lambda *args: tuple(args)
    qtcore.QEvent = SimpleNamespace(Type=SimpleNamespace(KeyPress=1,
                                                        MouseButtonPress=2))
    qtcore.Qt = qt
    qtcore.QTimer = SimpleNamespace(singleShot=lambda _delay, fn: fn())
    qtgui = ModuleType('PySide6.QtGui')
    class FakeStandardItem(Item):
        def __init__(self, icon, text):
            super().__init__(text, {})
            self._icon = icon
        def setEditable(self, *_):
            pass
        def setToolTip(self, tip):
            self._tooltip = tip
        def setData(self, value, role):
            if role == 101:
                self.meta = value
            elif role == 102:
                self.loaded = value
        def icon(self):
            return self._icon
        def toolTip(self):
            return getattr(self, '_tooltip', self.name)
        def appendRow(self, child):
            self.children.append(child)
            child._parent = self
        def parent(self):
            return getattr(self, '_parent', None)
    qtgui.QStandardItem = FakeStandardItem
    qtgui.QColor = lambda *args: None
    qtgui.QKeyEvent = lambda _type, key, mods: Event(key, modifiers=mods)
    class Painter:
        RenderHint = SimpleNamespace(Antialiasing=1)
        def __init__(self, *args): pass
        def setRenderHint(self, *args): pass
        def setFont(self, *args): pass
        def drawText(self, *args): pass
        def fillPath(self, *args): pass
        def end(self): pass
    class PainterPath:
        def moveTo(self, *args): pass
        def lineTo(self, *args): pass
        def closeSubpath(self): pass
    qtgui.QPainter = Painter
    qtgui.QPainterPath = PainterPath
    qtgui.QFont = lambda *args: args
    class FakePix:
        def __init__(self, *args): pass
        def setDevicePixelRatio(self, *args): pass
        def fill(self, *args): pass
    qtgui.QPixmap = FakePix
    class FakeRenderedIcon:
        def __init__(self, pix=None): self.pix = pix
        def isNull(self): return False
    qtgui.QIcon = FakeRenderedIcon
    qtwidgets = ModuleType('PySide6.QtWidgets')
    qtwidgets.QMenu = FakeQMenu
    class FakeLineEdit:
        def __init__(self, *args): self.textChanged = Signal();self.value = ''
        def setObjectName(self, *args): pass
        def setPlaceholderText(self, *args): pass
        def setClearButtonEnabled(self, *args): pass
        def setMinimumWidth(self, *args): pass
        def setStyleSheet(self, *args): pass
        def installEventFilter(self, *args): pass
        def backspace(self): self.value = self.value[:-1];self.textChanged.emit()
    class FakeWidgetAction(FakeAction):
        def __init__(self, *args): super().__init__()
        def setDefaultWidget(self, *args): pass
    class FakeRow:
        def __init__(self, text):
            self.caption = text
            self.hidden = False
            self.disabled = False
        def setSizeHint(self, *args): pass
        def setTextAlignment(self, column, value):
            self.text_alignment = (column, value)
        def setIcon(self, *args): pass
        def setToolTip(self, *args): pass
        def setDisabled(self, disabled): self.disabled = disabled
        def setHidden(self, hidden): self.hidden = hidden
        def isHidden(self): return self.hidden
    class FakeTree:
        def __init__(self, *args):
            self.rows=[]
            self.currentItemChanged=Signal()
            self.itemClicked=Signal()
            self.scrolled=[]
            self.selected=None
            self.fixed_width=None
            self.icon_size=None
            self.last_column_width=None
        def setFixedWidth(self, value): self.fixed_width=value
        def setFixedHeight(self, value): self.fixed_height=value
        def setIconSize(self, value): self.icon_size=value
        def setColumnWidth(self, column, value): self.last_column_width=(column, value)
        def __getattr__(self, name):
            if name.startswith('set') or name == 'installEventFilter':
                return lambda *args: None
            raise AttributeError(name)
        def header(self): return self
        def setSectionResizeMode(self, *args): pass
        def addTopLevelItem(self,row): self.rows.append(row)
        def viewport(self): return self
        def width(self): return 230
        def setCurrentItem(self, row):
            before=self.selected
            self.selected=row
            self.currentItemChanged.emit(row, before)
        def scrollToItem(self, row, hint):
            self.scrolled.append(row)
        def clearSelection(self):
            self.selected = None
        def visualItemRect(self, row):
            return SimpleNamespace(top=lambda: self.rows.index(row) * 29)
        def mapToGlobal(self, point): return point
        def setObjectName(self, *args): pass
    qtwidgets.QAbstractItemView = SimpleNamespace(
        ScrollMode=SimpleNamespace(ScrollPerPixel=1),
        SelectionMode=SimpleNamespace(SingleSelection=1),
        ScrollHint=SimpleNamespace(EnsureVisible=1))
    qtwidgets.QHeaderView = SimpleNamespace(
        ResizeMode=SimpleNamespace(Stretch=1, Fixed=2))
    qtwidgets.QTreeWidgetItem = FakeRow
    qtwidgets.QTreeWidget = FakeTree
    qtwidgets.QLineEdit = FakeLineEdit
    class FakeHolder:
        def __init__(self, parent=None): self.parent = parent
        def setObjectName(self, *args): pass
    class FakeHBoxLayout:
        def __init__(self, parent=None): self.parent = parent
        def setContentsMargins(self, *args): pass
        def setSpacing(self, *args): pass
        def addWidget(self, *args): pass
    qtwidgets.QWidget = FakeHolder
    qtwidgets.QHBoxLayout = FakeHBoxLayout
    qtwidgets.QWidgetAction = FakeWidgetAction
    class FakeApplication:
        def __init__(self):
            self.filters = []
            self.applicationStateChanged = Signal()
            self._state = qt.ApplicationState.ApplicationActive
        def installEventFilter(self, filter_obj): self.filters.append(filter_obj)
        def removeEventFilter(self, filter_obj): self.filters.remove(filter_obj)
        def applicationState(self): return self._state
    application = FakeApplication()
    qtwidgets.QApplication = SimpleNamespace(instance=lambda: application,
        sendEvent=lambda *args: None,
        screenAt=lambda pos: None, primaryScreen=lambda: SimpleNamespace(
            availableGeometry=lambda: SimpleNamespace(left=lambda: 0, right=lambda: 1200,
                width=lambda: 1201, top=lambda: 0, bottom=lambda: 800)))
    pyside = ModuleType('PySide6')
    monkeypatch.setitem(__import__('sys').modules, 'PySide6', pyside)
    monkeypatch.setitem(__import__('sys').modules, 'PySide6.QtCore', qtcore)
    monkeypatch.setitem(__import__('sys').modules, 'PySide6.QtGui', qtgui)
    monkeypatch.setitem(__import__('sys').modules, 'PySide6.QtWidgets', qtwidgets)
    virtual = ModuleType('launch_virtual_tree')
    virtual.virtual_item_identity = lambda node: {'source': 'launch_json',
                                                  'node_id': node['node_id']}
    monkeypatch.setitem(__import__('sys').modules, 'launch_virtual_tree', virtual)
    styling = ModuleType('context_menu_presentation')
    styling.style_context_menu = lambda menu, theme: menu
    monkeypatch.setitem(__import__('sys').modules, 'context_menu_presentation', styling)
    spec = importlib.util.spec_from_file_location('slash_exp_navigation_test', MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, key


def make_launcher():
    calls = []
    launcher = SimpleNamespace(color_theme='light', height=lambda: 650,
                               _slash_exp_navigation_menu=None,
                               row_icon=lambda _row: 'icon')
    launcher.navigate_files_exp_folder = lambda path, **kw: calls.append(('commit_folder', path))
    launcher.navigate_virtual_launch_folder = lambda node: calls.append(('commit_virtual', node))
    launcher.navigate_files_exp_pc = lambda: calls.append(('commit_pc', None))
    launcher.show_slash_exp_terminal_context = lambda path, pos, identity=None, return_menu=False: calls.append(('context_folder', path)) or FakeQMenu()
    launcher.show_files_exp_authored_root_menu = lambda path, identity, pos: calls.append(('context_authored', path))
    launcher.show_virtual_launch_context = lambda identity, pos, return_menu=False: calls.append(('context_virtual', identity)) or FakeQMenu()
    launcher.activate_virtual_launch_item = lambda row: calls.append(('execute_virtual', row))
    launcher.show_slash_exp_file_context = lambda path, pos, return_menu=False: calls.append(('context_file', path)) or FakeQMenu()
    launcher.run_file_path = lambda row, path: calls.append(('execute_file', path))
    return launcher, calls


def test_only_the_slash_character_starts_the_new_mode(nav):
    mod, key = nav
    assert mod.is_slash_shortcut(key.Key_Slash, '/', 0)
    assert mod.is_slash_shortcut(key.Key_Slash, '/', 1)
    assert mod.is_slash_shortcut(key.Key_Slash, '', 0)
    assert not mod.is_slash_shortcut(key.Key_Slash, '?', 1)
    assert not mod.is_slash_shortcut(key.Key_Slash, '/', 2)
    assert not mod.is_slash_shortcut(key.Key_Right, '', 0)


def test_right_moves_without_committing_intermediate_folders(nav, tmp_path):
    mod, key = nav
    path = str(tmp_path)
    leaf = Item('Final', {'path': path, 'pc': False}, Item('inner', {'file': True, 'path': str(tmp_path / 'x.txt')}))
    (tmp_path / 'x.txt').write_text('hi')
    branch = Item('Sub', {'virtual': {'node_id': 'sub'}, 'pc': False}, leaf)
    page = Item('First Level', {'virtual': {'node_id': 'page'}, 'pc': False}, branch)
    launcher, calls = make_launcher()
    panel = Panel([page])
    menu = mod.SlashExpMenu(launcher, panel)
    menu.populate()
    menu.popup((5, 5))
    menu.setActiveAction(next(iter(menu._action_items)))

    # Right traverses; Enter now intentionally opens the branch in Files List.
    menu.keyPressEvent(Event(key.Key_Right))
    second = menu.activeAction().menu()
    assert second.visible
    second.keyPressEvent(Event(key.Key_Right))
    third = second.activeAction().menu()
    assert third.visible
    assert calls == []  # Only arrows so far, nothing executed.

    third.keyPressEvent(Event(key.Key_Right))
    fourth = third.activeAction().menu()
    assert fourth.visible
    fourth.keyPressEvent(Event(key.Key_Down))  # Skip the parent self-context.
    fourth.keyPressEvent(Event(key.Key_Right))
    assert calls == [('context_file', str(tmp_path / 'x.txt'))]
    # A context menu is now ATTACHED as the next column, not abandoned.
    assert menu.visible
    assert fourth.activeAction().menu() is not None


def test_only_terminal_enter_opens_folder(nav, tmp_path):
    mod, key = nav
    leaf = Item('Final', {'path': str(tmp_path), 'pc': False})
    page = Item('Page', {'virtual': {'node_id': 'page'}}, leaf)
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([page]))
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    child = menu.activeAction().menu()
    child.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('commit_folder', str(tmp_path))]
    assert not menu.visible


def test_virtual_terminal_right_opens_existing_virtual_context(nav):
    mod, key = nav
    leaf = Item('Category', {'virtual': {'node_id': 'cat'}})
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([leaf]))
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    assert calls == [('context_virtual', {'source': 'launch_json', 'node_id': 'cat'})]


def test_left_goes_back_one_level_and_esc_dismisses_all(nav):
    mod, key = nav
    child = Item('Child', {'virtual': {'node_id': 'child'}})
    parent = Item('Parent', {'virtual': {'node_id': 'parent'}}, child)
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([parent]))
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    sub = menu.activeAction().menu()
    sub.keyPressEvent(Event(key.Key_Left))
    assert menu.visible and not sub.visible
    assert menu.activeAction() in menu._action_items
    menu.keyPressEvent(Event(key.Key_Escape))
    assert not menu.visible
    assert calls == []


def test_terminal_enter_carries_exp_origin_instead_of_stale_current(nav, tmp_path):
    mod, key = nav
    leaf = Item('Different registered root', {'path': str(tmp_path), 'pc': False})
    launcher, calls = make_launcher()
    origin = []
    launcher.navigate_files_exp_folder = lambda path, **kwargs: origin.append((path, kwargs))
    panel = Panel([leaf])
    menu = mod.SlashExpMenu(launcher, panel)
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Enter))
    assert calls == []
    assert len(origin) == 1
    assert origin[0][0] == str(tmp_path)
    assert origin[0][1]['origin_item'] is leaf
    assert origin[0][1]['origin_panel'] is panel


def test_json_virtual_executable_leaves_visible_and_enter_executes(nav):
    mod, key = nav
    leaf_node = {'source': 'launch_json', 'kind': 'file', 'page_id': 'work',
                 'item_id': 'zip_make', 'node_id': 'item:work:zip_make',
                 'title': 'ZIPを作る', 'row': {'page_id': 'work',
                                         'item_id': 'zip_make', 'title': 'ZIPを作る'}}
    zip_node = {'source': 'launch_json', 'kind': 'folder', 'page_id': 'work',
                'item_id': 'zip', 'node_id': 'item:work:zip', 'title': 'ZIP',
                'children': [leaf_node]}
    zip_item = Item('ZIP', {'virtual': zip_node})
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([zip_item]))
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    # New requirement: ENTER on a branch shows it in Files List.
    menu.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('commit_virtual', zip_node)]
    calls.clear()
    menu.keyPressEvent(Event(key.Key_Right))
    sub = menu._submenus[next(iter(menu._action_items))]
    assert sub.visible
    assert [item.text() for item in sub._action_items.values()] == ['（カレントフォルダー）', 'ZIPを作る']
    sub.setActiveAction(list(sub._action_items)[1])
    sub.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('execute_virtual', leaf_node['row'])]


def test_up_down_cannot_open_any_child_menu_without_right(nav):
    mod, key = nav
    one = {'kind': 'file', 'node_id': 'one', 'title': 'one', 'row': {'item_id': 'one'}}
    two = {'kind': 'file', 'node_id': 'two', 'title': 'two', 'row': {'item_id': 'two'}}
    first = Item('First', {'virtual': {'kind': 'folder', 'children': [one], 'node_id': 'first'}})
    second = Item('Second', {'virtual': {'kind': 'folder', 'children': [two], 'node_id': 'second'}})
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([first, second]))
    menu.populate()
    menu.popup((0, 0))
    selected = list(menu._action_items)
    menu.setActiveAction(selected[0])
    assert all(action.menu() is None for action in selected)
    menu.keyPressEvent(Event(key.Key_Down))
    assert menu.activeAction() is selected[1]
    assert not menu._submenus[selected[1]].visible
    menu.keyPressEvent(Event(key.Key_Up))
    assert menu.activeAction() is selected[0]
    assert not menu._submenus[selected[0]].visible
    assert calls == []


def test_physical_file_is_last_level(nav, tmp_path):
    mod, key = nav
    f = tmp_path / 'test.txt'
    f.write_text('hello')
    parent = Item('root-directory', {'path': str(tmp_path), 'pc': False})
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([parent]))
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    child = menu._submenus[next(iter(menu._action_items))]
    assert [item.text() for item in child._action_items.values()] == ['（カレントフォルダー）', 'test.txt']
    child.setActiveAction(list(child._action_items)[1])
    child.keyPressEvent(Event(key.Key_Right))
    assert ('context_file', str(f)) in calls


def test_terminal_has_no_fake_right_arrow_and_icons_keep_native_left_lane(nav):
    mod, key = nav
    terminal = Item('JSON設定', {'virtual': {'source': 'launch_json',
                                 'kind': 'file', 'node_id': 'leaf',
                                 'row': {'item_id': 'settings'}}})
    branch = Item('With child', {'virtual': {'kind': 'folder',
                  'node_id': 'branch', 'children': [{'kind': 'file', 'title': 'child',
                                                   'node_id': 'child', 'row': {}}]}})
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([terminal, branch]))
    menu.populate()
    actions = list(menu._action_items)
    assert '▸' not in actions[0].caption
    assert actions[0] not in menu._submenus
    assert actions[0]._icon == 'folder-icon'  # Native Qt icon to left.
    assert actions[1] in menu._submenus
    assert '▸' not in actions[1].caption  # One painted chevron, not text+native.


def test_slash_closes_entire_open_navigation_and_search_filters_this_column(nav):
    mod, key = nav
    first = Item('FRB', {'virtual': {'kind': 'file', 'node_id': 'frb'}})
    second = Item('ZIP', {'virtual': {'kind': 'file', 'node_id': 'zip'}})
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([first, second]))
    menu.populate()
    menu.popup((0, 0))
    menu._filter_rows('zip')
    actions = list(menu._action_items)
    assert not actions[0].isVisible()
    assert actions[1].isVisible()
    assert menu.activeAction() is actions[1]
    menu._filter_rows('')
    assert all(action.isVisible() for action in actions)
    menu.keyPressEvent(Event(key.Key_Slash))
    assert not menu.visible
    assert calls == []


def test_shift_slash_closes_without_escaping_to_exp(nav):
    mod, key = nav
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([Item('A', {'file': True})]))
    menu.popup((0, 0))
    event = Event(key.Key_Slash, text='/', modifiers=1)
    menu.keyPressEvent(event)
    assert event.accepted and not menu.visible


def test_terminal_context_is_aligned_child_and_keyboard_enter_triggers_original(nav):
    mod, key = nav
    terminal = Item('leaf', {'virtual': {'kind': 'file', 'node_id': 'leaf',
                                         'row': {'item_id': 'leaf'}}})
    launcher, calls = make_launcher()
    original_context = FakeQMenu()
    action = original_context.addAction('詳細編集...')
    action.triggered.connect(lambda: calls.append(('context_execute', 'detail')))
    launcher.show_virtual_launch_context = lambda *args, **kwargs: original_context
    root = mod.SlashExpMenu(launcher, Panel([terminal]))
    root.populate()
    root.popup((10, 10))
    root.setActiveAction(next(iter(root._action_items)))
    root.keyPressEvent(Event(key.Key_Right))
    child = root.activeAction().menu()
    assert isinstance(child, mod.SlashExpMenu)
    assert child._context_source is original_context
    assert child.parent is root
    assert child.visible
    assert child.activeAction() is not None
    assert calls == []
    child.keyPressEvent(Event(key.Key_Enter))
    assert ('context_execute', 'detail') in calls
    assert not root.visible


def test_context_submenus_are_further_nonexecuting_levels(nav):
    mod, key = nav
    leaf = Item('leaf', {'virtual': {'kind': 'file', 'node_id': 'leaf', 'row': {}}})
    launcher, calls = make_launcher()
    original_context = FakeQMenu()
    new_submenu = FakeQMenu()
    new_action = original_context.addAction('新規作成')
    new_action.setMenu(new_submenu)
    new_command = new_submenu.addAction('フォルダー')
    new_command.triggered.connect(lambda: calls.append('created'))
    launcher.show_virtual_launch_context = lambda *args, **kwargs: original_context
    root = mod.SlashExpMenu(launcher, Panel([leaf]))
    root.populate()
    root.popup((0, 0))
    root.setActiveAction(next(iter(root._action_items)))
    root.keyPressEvent(Event(key.Key_Right))
    context = root.activeAction().menu()
    context.keyPressEvent(Event(key.Key_Enter))
    assert calls == []  # Enter on the intermediate context branch is inert.
    context.keyPressEvent(Event(key.Key_Right))
    deeper = context.activeAction().menu()
    assert isinstance(deeper, mod.SlashExpMenu)
    deeper.keyPressEvent(Event(key.Key_Enter))
    assert calls == ['created']


def test_context_text_elides_without_losing_full_filter(nav):
    mod, key = nav
    launcher, _ = make_launcher()
    leaf = Item('leaf', {'virtual': {'kind': 'file', 'node_id': 'leaf', 'row': {}}})
    original_context = FakeQMenu()
    original = original_context.addAction('本当にとても長いコンテキストメニューの操作名のままにしておく')
    launcher.show_virtual_launch_context = lambda *args, **kwargs: original_context
    menu = mod.SlashExpMenu(launcher, Panel([leaf]))
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    context = menu.activeAction().menu()
    display = next(iter(context._action_items))
    assert display.caption != original.text()
    assert display.caption.endswith('…')
    assert context._full_text[display] == original.text()
    context._filter_rows('コンテキストメニュー')
    assert display.isVisible()


def test_search_column_uses_real_layout_inside_menu(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([]))
    menu.populate()
    assert menu.fixed_width == mod.SLASH_STANDARD_WIDTH
    assert menu._search_action is not None
    assert menu._search_edit is not None


def test_terminal_context_is_positioned_beside_selected_row(nav):
    mod, key = nav
    launcher, _ = make_launcher()
    leaf = Item('leaf', {'virtual': {'kind': 'file', 'node_id': 'leaf', 'row': {}}})
    source = FakeQMenu()
    source.addAction('簡易編集')
    launcher.show_virtual_launch_context = lambda *args, **kwargs: source
    menu = mod.SlashExpMenu(launcher, Panel([leaf]))
    menu.populate()
    menu.popup((25, 25))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    context = menu.activeAction().menu()
    # Commands now float near the visible caption, not at the full column edge.
    assert context.moved[0].x() == menu._operation_popup_x(menu.activeAction())
    assert context.moved[0].x() < menu.width() - 1
    assert context.moved[0].y() == 10  # Taskbar/work-area safety inset.


def test_unbranched_menu_item_has_no_open_submenu_and_enter_is_direct(nav):
    mod, key = nav
    leaf = Item('実行する', {'virtual': {'kind': 'file', 'node_id': 'leaf',
                                        'row': {'item_id': 'run'}}})
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([leaf]))
    menu.populate()
    menu.popup((0, 0))
    action = next(iter(menu._action_items))
    menu.setActiveAction(action)
    assert action not in menu._submenus
    menu.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('execute_virtual', {'item_id': 'run'})]
    assert not menu.visible


def test_root_reserves_horizontal_space_for_third_context_column(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    root = Item('root', {'virtual': {'kind': 'folder', 'node_id': 'root',
                                   'children': [{'kind': 'file', 'node_id': 'leaf',
                                                 'title': 'leaf', 'row': {}}]}})
    point = mod.QPoint(830, 50)
    assert mod.popup_exp_navigator(launcher, Panel([root]), point)
    popup = launcher._slash_exp_navigation_menu
    assert popup is not None
    # Keep caller-chosen List Name-column anchor, rather than pulling the root
    # far left to reserve four imaginary, possibly wide child columns.
    assert popup.popup_point.x() == 830
    assert popup.popup_point.x() + popup.width() <= 1201


def test_mouse_branch_click_opens_instead_of_dismissing(nav):
    mod, _ = nav
    child = Item('child', {'virtual': {'kind': 'file', 'node_id': 'child',
                                     'row': {'item_id': 'child'}}})
    parent = Item('parent', {'virtual': {'kind': 'folder', 'node_id': 'parent'}}, child)
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([parent]))
    menu.populate()
    menu.popup((0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    event = SimpleNamespace(button=lambda: 1,
                            position=lambda: SimpleNamespace(toPoint=lambda: (1, 1)),
                            accept=lambda: None)
    menu.mouseReleaseEvent(event)
    assert menu.visible
    assert menu.activeAction().menu().visible
    assert not calls


def test_page_emojis_are_moved_into_real_left_icon_lane(nav):
    mod, _ = nav
    assert mod.leading_page_emoji('💼 My Work') == ('💼', 'My Work')
    assert mod.leading_page_emoji('🪟 Windows') == ('🪟', 'Windows')
    assert mod.leading_page_emoji('🎣FRB実験') == ('🎣', 'FRB実験')
    assert mod.leading_page_emoji('普通のフォルダー') == ('', '普通のフォルダー')
    class IconlessItem(Item):
        def icon(self): return FakeIcon()
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([
        IconlessItem('💼 My Work', {'virtual': {'kind': 'page', 'node_id': 'one'}}),
        IconlessItem('無印設定', {'virtual': {'kind': 'file', 'node_id': 'two'}}),
    ]))
    menu.populate()
    action_emoji, action_plain = list(menu._action_items)
    assert action_emoji.caption == 'My Work'
    assert not action_emoji.icon().isNull()
    assert action_emoji not in menu._iconless_actions
    assert action_plain in menu._iconless_actions
    assert menu._full_text[action_emoji] == '💼 My Work'


def test_opened_submenu_position_is_pinned_during_arrow_scroll(nav):
    mod, key = nav
    launcher, _ = make_launcher()
    leaf = Item('Child', {'virtual': {'kind': 'file', 'node_id': 'leaf', 'row': {}}})
    root = Item('Root', {'virtual': {'kind': 'folder', 'node_id': 'root'}}, leaf)
    menu = mod.SlashExpMenu(launcher, Panel([root]))
    menu.populate()
    menu.popup(mod.QPoint(20, 100))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    submenu = menu.activeAction().menu()
    pinned = submenu._fixed_popup_pos
    assert pinned is not None
    # Simulate a native QMenu scroll reposition: it must restore the *same*
    # point, rather than following the selected item or rebuilding the popup.
    submenu.move(mod.QPoint(pinned.x(), pinned.y()-180))
    submenu.moveEvent(None)
    assert submenu.pos() == pinned
    submenu.keyPressEvent(Event(key.Key_Down))
    assert submenu._fixed_popup_pos == pinned


def test_virtual_url_uses_files_list_third_column_preview_before_launch(nav):
    mod, key = nav
    node = {'kind': 'file', 'node_id': 'url', 'row': {'item_id': 'url', 'page_id': 'page'}}
    launcher, calls = make_launcher()
    previews = []
    launcher.expanded_view = SimpleNamespace(
        preview_bookmark_from_list=lambda row: previews.append(row) or True)
    leaf = Item('Open URL', {'virtual': node})
    menu = mod.SlashExpMenu(launcher, Panel([leaf]))
    menu.populate()
    menu.popup(mod.QPoint(5, 10))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Enter))
    assert previews == [{'_launch_virtual_node': node}]
    assert calls == []  # Browser preview wins; no external URL launch.
    assert not menu.visible


def test_nonurl_leaf_falls_back_to_original_list_activation(nav):
    mod, key = nav
    node = {'kind': 'file', 'node_id': 'command', 'row': {'item_id': 'command'}}
    launcher, calls = make_launcher()
    launcher.expanded_view = SimpleNamespace(preview_bookmark_from_list=lambda row: False)
    menu = mod.SlashExpMenu(launcher, Panel([Item('Run', {'virtual': node})]))
    menu.populate()
    menu.popup(mod.QPoint(5, 10))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('execute_virtual', node['row'])]


def test_launch_first_slash_column_opens_at_files_list_name_header():
    """Test the actual Launch method without importing the GUI-heavy app."""
    import ast
    app = (ROOT / 'src' / 'app.py').read_text('utf-8')
    tree = ast.parse(app)
    method = next(n for cls in tree.body if isinstance(cls, ast.ClassDef)
                  for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'show_slash_exp_navigation_menu')
    namespace = {}
    class Point:
        def __init__(self, x, y): self._x, self._y = x, y
        def x(self): return self._x
        def y(self): return self._y
    calls = []
    namespace['QPoint'] = Point
    source = object()  # Already resolved from the logical breadcrumb.
    namespace['slash_source_from_breadcrumb'] = lambda launcher, view, panel: source
    namespace['slash_source_with_filled_list_folder'] = lambda launcher, view, source: source
    namespace['slash_popup_row_anchor'] = lambda view, panel, source, base: None
    namespace['popup_exp_navigator'] = lambda launcher, panel, anchor, **kw: calls.append((anchor, kw)) or True
    expression = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(expression, '<Launch slash position>', 'exec'), namespace)
    panel = SimpleNamespace(model=SimpleNamespace(rowCount=lambda: 7),
        tree=SimpleNamespace(isVisible=lambda: True, width=lambda: 240,
            mapToGlobal=lambda point: Point(25 + point.x(), 180 + point.y())))
    name_header = SimpleNamespace(isVisible=lambda: True,
        isSectionHidden=lambda col: False, sectionViewportPosition=lambda col: 0,
        sectionSize=lambda col: 310,
        mapToGlobal=lambda point: Point(310 + point.x(), 126 + point.y()))
    view = SimpleNamespace(isVisible=lambda: True, _workspace_mode='files',
        embedded_files_exp=panel,
        middle=SimpleNamespace(tree=SimpleNamespace(header=lambda: name_header,
            viewport=lambda: SimpleNamespace(height=lambda: 640,
                mapToGlobal=lambda p: Point(310+p.x(), 150+p.y())))))
    pad = SimpleNamespace(isVisible=lambda: True, width=lambda: 60,
                          mapToGlobal=lambda point: Point(390, 515))
    dummy = SimpleNamespace(expanded_view=view,
        _current_remote_files_exp=lambda: panel,
        close_remote_folder_menu=lambda: None, close_remote_page_menu=lambda: None,
        _active_remote_wheel_pad=lambda: pad, _launch_context_menu=None,
        menu=None, _slash_exp_navigation_menu=None)
    assert namespace['show_slash_exp_navigation_menu'](dummy)
    assert len(calls) == 1
    assert calls[0][0].x() == 310  # List Name header's left edge.
    assert calls[0][0].y() == 126
    assert calls[0][1]['source_item'] is source
    assert calls[0][1]['first_column_width'] == 310
    assert calls[0][1]['list_height'] == 640


def test_long_column_scrolls_selected_item_inside_fixed_viewport(nav):
    mod, key = nav
    launcher, calls = make_launcher()
    leaves = [Item('file%03d.txt' % index, {'file': True,
                  'path': '/nonexistent/file%03d.txt' % index}) for index in range(90)]
    menu = mod.SlashExpMenu(launcher, Panel(leaves))
    menu.populate()
    assert menu._scroll_tree is not None
    assert len(menu._scroll_tree.rows) == 90
    old_pos = mod.QPoint(90, 130)
    menu.popup(old_pos)
    assert menu.pos() == old_pos
    for index in range(50):
        menu.keyPressEvent(Event(key.Key_Down))
    assert menu._scroll_tree.scrolled[-1] == menu._scroll_tree.rows[50]
    assert menu.pos() == old_pos, 'Only rows, not the menu window, should scroll'
    assert calls == []


def test_physical_markdown_and_studio_json_use_same_files_list_preview(nav, tmp_path):
    mod, key = nav
    launcher, calls = make_launcher()
    previews = []
    launcher.expanded_view = SimpleNamespace(
        preview_bookmark_from_list=lambda row: previews.append(row) or True)
    for filename in ('note.md', 'studio_work.json'):
        path = tmp_path / filename
        path.write_text('test', encoding='utf-8')
        menu = mod.SlashExpMenu(launcher, Panel([Item(filename, {'path': str(path),
                                                                 'file': True})]))
        menu.populate()
        menu.popup(mod.QPoint(5, 10))
        menu.setActiveAction(next(iter(menu._action_items)))
        menu.keyPressEvent(Event(key.Key_Enter))
    assert [item['_browse_file'] for item in previews] == [
        str(tmp_path / 'note.md'), str(tmp_path / 'studio_work.json')]
    assert calls == [], 'Avoid bypassing Files List to launch standalone'


def test_physical_preview_fallback_preserves_native_executor(nav, tmp_path):
    mod, key = nav
    path = tmp_path / 'ordinary.py'
    path.write_text('x=1')
    launcher, calls = make_launcher()
    launcher.expanded_view = SimpleNamespace(preview_bookmark_from_list=lambda row: False)
    menu = mod.SlashExpMenu(launcher, Panel([Item(path.name, {'path': str(path), 'file': True})]))
    menu.populate()
    menu.popup(mod.QPoint(5, 10))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('execute_file', str(path))]


def test_long_folder_column_right_enters_child_without_scrolling_popup(nav):
    mod, key = nav
    launcher, calls = make_launcher()
    leaves = [Item('File%03d' % i,
                   {'virtual': {'kind': 'folder', 'node_id': 'folder%03d' % i,
                                'children': [{'kind': 'file', 'node_id': 'cmd%03d' % i,
                                              'title': 'run', 'row': {'item_id': str(i)}}]}})
              for i in range(70)]
    menu = mod.SlashExpMenu(launcher, Panel(leaves))
    menu.populate()
    menu.popup(mod.QPoint(30, 80))
    for _ in range(32):
        menu.keyPressEvent(Event(key.Key_Down))
    action, item = menu._selected()
    assert item is leaves[32]
    menu.keyPressEvent(Event(key.Key_Right))
    child = menu._submenus[action]
    assert child.isVisible()
    assert menu._scroll_action.menu() is child
    assert child._fixed_popup_pos is not None
    assert menu.pos() == mod.QPoint(30, 80)
    child.keyPressEvent(Event(key.Key_Left))
    assert menu.isVisible() and not child.isVisible()
    assert menu._selected()[0] is action
    assert calls == []


def test_long_column_search_filters_and_selection_scrolls_to_match(nav):
    mod, key = nav
    launcher, calls = make_launcher()
    leaves = [Item('file%03d.txt' % i, {'file': True, 'path': '/no/file'})
              for i in range(90)]
    menu = mod.SlashExpMenu(launcher, Panel(leaves))
    menu.populate()
    menu._filter_rows('file087')
    assert menu._selected()[1].text() == 'file087.txt'
    assert len(menu._visible_rows()) == 1
    assert menu._scroll_tree.scrolled[-1] is menu._scroll_tree.rows[87]
    menu._filter_rows('')
    assert len(menu._visible_rows()) == 90
    assert calls == []


def test_downloads_like_directory_does_not_truncate_140_physical_files(nav, tmp_path):
    mod, key = nav
    folder = tmp_path / 'Downloads'
    folder.mkdir()
    for index in range(140):
        (folder / f'file_{index:03d}.md').write_text('hello', encoding='utf8')
    subdir = folder / 'notes'
    subdir.mkdir()
    launcher, calls = make_launcher()
    parent = Item('Downloads', {'path': str(folder), 'pc': False},
                  Item('notes', {'path': str(subdir), 'pc': False}))
    menu = mod.SlashExpMenu(launcher, Panel([parent]))
    menu.populate()
    menu.popup(mod.QPoint(100, 120))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    child = menu._submenus[next(iter(menu._action_items))]
    assert len(child._action_items) == 142, 'The view height must not truncate results'
    assert len(child._scroll_tree.rows) == 142
    assert {i.text() for i in child._action_items.values()} == {
        '（カレントフォルダー）', 'notes', *(f'file_{index:03d}.md' for index in range(140))}
    point_before = child.pos()
    for _ in range(128):
        child.keyPressEvent(Event(key.Key_Down))
    assert child._selected()[1].text() == 'file_126.md'
    assert child.pos() == point_before, 'Only the inner viewport scrolls'
    assert child._scroll_tree.scrolled[-1] is child._scroll_items[child._selected()[0]]
    assert calls == []


def test_large_folder_search_reveals_all_rows_when_cleared(nav):
    mod, key = nav
    launcher, calls = make_launcher()
    entries = [Item(f'download_{i:03d}', {'file': True, 'path': f'/x/{i}'})
               for i in range(120)]
    menu = mod.SlashExpMenu(launcher, Panel(entries))
    menu.populate()
    assert len(menu._visible_rows()) == 120
    menu._filter_rows('download_109')
    assert len(menu._visible_rows()) == 1
    assert menu._selected()[1].text() == 'download_109'
    menu._filter_rows('unmatched_file_name')
    assert menu._visible_rows() == []
    assert menu._selected() == (None, None)
    menu._filter_rows('')
    assert len(menu._visible_rows()) == 120
    assert menu._selected()[1].text() == 'download_000'
    menu.keyPressEvent(Event(key.Key_Down))
    assert menu._selected()[1].text() == 'download_001'
    assert calls == []


def test_menu_width_uses_two_text_driven_modes_independent_of_scrollbar(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    short_rows = [Item('短い' + str(i), {'file': True}) for i in range(120)]
    standard = mod.SlashExpMenu(launcher, Panel(short_rows))
    standard.populate()
    assert standard.width() == mod.SLASH_STANDARD_WIDTH
    assert standard._scroll_tree is not None
    assert standard._scroll_tree.fixed_width == standard.width() - 18
    assert standard._scroll_tree.last_column_width == (1, 22)
    # Even in scrollbar mode, the arrow occupies a dedicated, right-aligned
    # fixed column; it does not steal width from the caption column.
    assert standard._scroll_tree.rows[0].text_alignment[0] == 1

    filename = 'ai-collaboration16-very-very-long-file-name-for-exp-navigation.md'
    long_rows = [Item(filename, {'file': True})]
    wide = mod.SlashExpMenu(launcher, Panel(long_rows))
    wide.populate()
    assert wide.width() == mod.SLASH_LONG_WIDTH
    assert wide.width() == standard.width()  # Both set to 300px by current UI decision.
    first = next(iter(wide._action_items))
    assert wide._full_text[first] == filename  # Unabridged for search/tooltips
    assert first.text().endswith('…')
    assert len(first.text()) > 20  # A readable prefix, not ~10 characters


def test_long_column_width_is_preserved_when_scrollbar_is_present(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    long_rows = [Item('fft_log_ダイソー120_1_長いファイル名称-%03d.json' % n,
                      {'file': True}) for n in range(140)]
    menu = mod.SlashExpMenu(launcher, Panel(long_rows))
    menu.populate()
    assert menu.width() == mod.SLASH_LONG_WIDTH
    assert menu._scroll_tree is not None
    assert menu._scroll_tree.fixed_width == mod.SLASH_LONG_WIDTH - 18
    assert len(menu._scroll_tree.rows) == 140
    # The text width is computed from the wider menu, regardless of whether
    # the rows are rendered inside QMenu or its scroll widget.
    action = next(iter(menu._action_items))
    assert len(action.text()) > 20


def test_first_slash_menu_tracks_name_column_even_without_visible_wheel():
    import ast
    code = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    method = next(n for cls in ast.parse(code).body if isinstance(cls, ast.ClassDef)
                  for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'show_slash_exp_navigation_menu')
    class Point:
        def __init__(self,x,y): self._x=x;self._y=y
        def x(self): return self._x
        def y(self): return self._y
    seen=[]
    source = object()
    namespace={'QPoint': Point,
               'slash_source_from_breadcrumb': lambda obj, view, panel: source,
               'slash_source_with_filled_list_folder': lambda obj, view, source: source,
               'slash_popup_row_anchor': lambda view, panel, source, base: None,
               'popup_exp_navigator': lambda obj, panel, anchor, **kw: seen.append((anchor, kw)) or True}
    compiled=ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(compiled,'<slash overlay test>','exec'),namespace)
    viewport=SimpleNamespace(isVisible=lambda: True,
                             mapToGlobal=lambda p: Point(125+p.x(),215+p.y()))
    tree=SimpleNamespace(isVisible=lambda: True, width=lambda: 264,
                         mapToGlobal=lambda p: Point(125+p.x(), 215+p.y()))
    panel=SimpleNamespace(model=SimpleNamespace(rowCount=lambda: 3), tree=tree)
    name_header=SimpleNamespace(isVisible=lambda: True,
        isSectionHidden=lambda col: False,
        sectionViewportPosition=lambda col: 84 if col == 0 else 0,
        sectionSize=lambda col: 415 if col == 0 else 156,
        mapToGlobal=lambda p: Point(320+p.x(), 125+p.y()))
    view=SimpleNamespace(isVisible=lambda: True, _workspace_mode='files',
        embedded_files_exp=panel,
        middle=SimpleNamespace(tree=SimpleNamespace(header=lambda: name_header,
            viewport=lambda: SimpleNamespace(height=lambda: 500,
                mapToGlobal=lambda p: Point(320+p.x(), 155+p.y())))))
    obj=SimpleNamespace(expanded_view=view,
                        _current_remote_files_exp=lambda: panel,
                        close_remote_folder_menu=lambda: None,
                        close_remote_page_menu=lambda: None,
                        _launch_context_menu=None, menu=None,
                        _slash_exp_navigation_menu=None)
    assert namespace['show_slash_exp_navigation_menu'](obj)
    assert (seen[0][0].x(),seen[0][0].y()) == (404,125)
    assert seen[0][1]['first_column_width'] == 415
    assert seen[0][1]['list_height'] == 500
    assert seen[0][1]['source_item'] is source


def test_root_never_invents_current_folder_action(nav, tmp_path):
    mod, key = nav
    launcher, calls = make_launcher()
    launcher.expanded_view = SimpleNamespace(
        _virtual_directory_node={'kind': 'page', 'source': 'launch_json', 'title': 'My Work'},
        current_directory=lambda: str(tmp_path))
    menu = mod.SlashExpMenu(launcher, Panel([
        Item('My Work', {'virtual': {'kind': 'page', 'node_id': 'page'}}),
        Item('Downloads', {'path': str(tmp_path)})]))
    menu.populate()
    assert '（カレントフォルダー）' not in [item.text() for item in menu._action_items.values()]
    assert not calls


def test_opened_virtual_folder_adds_self_context_without_os_root_new(nav):
    mod, key = nav
    node = {'kind': 'folder', 'source': 'launch_json', 'node_id': 'folder',
            'page_id': 'work', 'item_id': 'folder', 'title': 'Docs',
            'children': [{'kind': 'file', 'node_id': 'md', 'title': 'README.md', 'row': {}}]}
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([Item('Docs', {'virtual': node})]))
    menu.populate()
    menu.popup(mod.QPoint(0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    sub = menu._submenus[next(iter(menu._action_items))]
    action = next(iter(sub._action_items))
    assert sub._action_items[action].text() == '（カレントフォルダー）'
    assert len(sub._action_items) == 2
    sub.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('commit_virtual', node)]
    calls.clear()
    sub.keyPressEvent(Event(key.Key_Right))
    assert calls == [('context_virtual', {'source': 'launch_json', 'node_id': 'folder'})]


def test_opened_physical_folder_context_uses_actual_selected_branch(nav, tmp_path):
    mod, key = nav
    launcher, calls = make_launcher()
    folder = tmp_path / 'sub'; folder.mkdir()
    (folder / 'hello.md').write_text('ok', encoding='utf-8')
    unrelated = tmp_path / 'unrelated'; unrelated.mkdir()
    launcher.expanded_view = SimpleNamespace(current_directory=lambda: str(unrelated))
    parent = Item('Downloads', {'path': str(folder), 'pc': False})
    menu = mod.SlashExpMenu(launcher, Panel([parent]))
    menu.populate()
    menu.popup(mod.QPoint(0, 0))
    menu.setActiveAction(next(iter(menu._action_items)))
    menu.keyPressEvent(Event(key.Key_Right))
    sub = menu._submenus[next(iter(menu._action_items))]
    sub.keyPressEvent(Event(key.Key_Right))
    assert calls == [('context_folder', str(folder))]


@pytest.mark.parametrize('name_width', [170, 300, 460])
def test_first_slash_popup_matches_list_name_width_instead_of_text_width(nav, name_width):
    mod, _ = nav
    launcher, _ = make_launcher()
    # A long label must not force the root above the Name-column width;
    # a short label must not shrink a wide user-resized Name column.
    label = 'long_named_file_' + ('abcdef' * 25) + '.md'
    panel = Panel([Item(label, {'file': True, 'path': '/not-a-real-file'})])
    anchor = mod.QPoint(311, 128)
    assert mod.popup_exp_navigator(
        launcher, panel, anchor, first_column_width=name_width)
    popup = launcher._slash_exp_navigation_menu
    assert popup.width() == name_width
    assert popup.popup_point == anchor
    assert popup._exact_first_column_width == name_width


def test_first_slash_popup_long_list_viewport_matches_resized_name_width(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    panel = Panel([Item('file%03d.md' % index, {'file': True})
                   for index in range(100)])
    assert mod.popup_exp_navigator(
        launcher, panel, mod.QPoint(320, 140), first_column_width=345)
    menu = launcher._slash_exp_navigation_menu
    assert menu.width() == 345
    assert menu._scroll_tree is not None
    assert menu._scroll_tree.fixed_width == menu.width() - 18


def test_second_slash_column_retains_own_auto_width(nav):
    mod, key = nav
    launcher, _ = make_launcher()
    child = Item('nested', {'file': True})
    folder = Item('folder', {'virtual': {'kind': 'folder', 'node_id': 'folder'}}, child)
    assert mod.popup_exp_navigator(
        launcher, Panel([folder]), mod.QPoint(322, 128), first_column_width=435)
    root = launcher._slash_exp_navigation_menu
    action = next(iter(root._action_items))
    root.setActiveAction(action)
    root.keyPressEvent(Event(key.Key_Right))
    submenu = root._submenus[action]
    assert root.width() == 435
    assert submenu.width() == mod.SLASH_STANDARD_WIDTH
    assert submenu._exact_first_column_width is None


def test_root_narrow_width_is_applied_before_scroll_viewport_creation(nav):
    mod, key = nav
    launcher, _ = make_launcher()
    roots = [Item(f'root-{i}', {'virtual': {'kind': 'file', 'node_id': f'{i}'}})
             for i in range(70)]
    menu = mod.SlashExpMenu(launcher, Panel(roots))
    menu._max_first_column_width = 222
    menu.populate()
    assert menu.width() == 222
    assert menu._scroll_tree.fixed_width == menu.width() - 18


def test_multi_selection_disables_single_item_launch_json_actions():
    text = (ROOT/'src'/'app.py').read_text('utf-8')
    assert "simple.setEnabled(len(selected_unregister) <= 1)" in text
    assert "properties_action.setEnabled(len(selected_unregister) <= 1)" in text
    assert "reference.setEnabled(bool(item_id) and len(selected_unregister) <= 1)" in text
    assert "launch_unregister_many_action(targets)" in text



def test_folder_branch_and_current_folder_enter_open_files_list(nav, tmp_path):
    mod, key = nav
    parent = tmp_path / 'parent'
    child = parent / 'child'
    child.mkdir(parents=True)
    branch = Item('Parent', {'path': str(parent), 'pc': False},
                  Item('Child', {'path': str(child), 'pc': False}))
    launcher, calls = make_launcher()
    root = mod.SlashExpMenu(launcher, Panel([branch]))
    root.populate()
    root.popup(mod.QPoint(0, 0))
    root.setActiveAction(next(iter(root._action_items)))
    root.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('commit_folder', str(parent))]
    calls.clear()
    # Right still opens children and the (カレントフォルダー) entry.
    root.keyPressEvent(Event(key.Key_Right))
    sub = root._submenus[next(iter(root._action_items))]
    sub.keyPressEvent(Event(key.Key_Enter))
    assert calls == [('commit_folder', str(parent))]


def test_slash_context_hides_files_list_only_not_original_source(nav):
    mod, _ = nav
    launcher, _calls = make_launcher()
    source = FakeQMenu()
    source.addAction('Filesリスト')
    source.addSeparator()
    source.addAction('新規作成')
    source.addAction('プロパティ')
    projected = mod.SlashExpMenu(launcher, Panel([]), context_source=source)
    projected.populate()
    assert [item.text() for item in projected._action_items.values()] == [
        '新規作成', 'プロパティ']
    assert [action.text() for action in source.actions() if not action.isSeparator()] == [
        'Filesリスト', '新規作成', 'プロパティ']
    assert not projected.actions()[1].isSeparator()  # No leading separator.


def test_slash_density_matches_files_list_not_launch_height(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    launcher.expanded_view = SimpleNamespace(row_density='compact')
    launcher.height = lambda: 140
    compact = mod.SlashExpMenu(launcher, Panel([]))
    assert compact._item_height == 27
    assert compact._popup_height >= 600  # Not 70% of 140px Launch height.
    launcher.height = lambda: 1500
    assert mod.SlashExpMenu(launcher, Panel([]))._item_height == 27
    launcher.expanded_view.row_density = 'normal'
    assert mod.SlashExpMenu(launcher, Panel([]))._item_height == 37
