"""Qt-free behaviour tests for Insert -> current folder and Menu-key routing.

Desktop acceptance on Windows is still needed for native ContextMenu delivery.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT/'src/app.py').read_text(encoding='utf-8')
VIEW = (ROOT/'src/expanded_view.py').read_text(encoding='utf-8')
SLASH = (ROOT/'src/slash_exp_navigation.py').read_text(encoding='utf-8')


def extract_method(src, class_name, method_name, env):
    cls = next(x for x in ast.parse(src).body
               if isinstance(x, ast.ClassDef) and x.name == class_name)
    fn = next(x for x in cls.body
              if isinstance(x, ast.FunctionDef) and x.name == method_name)
    mod = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    ns = dict(env)
    exec(compile(mod, '<extracted-production-method>', 'exec'), ns)
    return ns[method_name]


class Event:
    def __init__(self, kind, key=None, mods=0):
        self.kind, self.key_value, self.mods = kind, key, mods
        self.accepted = False
    def type(self): return self.kind
    def key(self): return self.key_value
    def modifiers(self): return self.mods
    def accept(self): self.accepted = True


class Widget:
    def __init__(self, parent=None, *, window=None, launcher=None):
        self.parent = parent
        self.owner_window = window
        if launcher is not None:
            self.launcher = launcher
    def parentWidget(self): return self.parent
    def window(self): return self.owner_window


def test_insert_uses_existing_tonton_clear_without_erasing_passive_cursor():
    calls=[]
    current=object()
    tree=NS(deliberate_blank_selection=False,
            clearSelection=lambda:calls.append('clear'),
            setFocus=lambda reason:calls.append(('focus',reason)),
            blank_clicked=lambda:calls.append('sync-directory'),
            currentItem=lambda:current,
            viewport=lambda:NS(update=lambda:calls.append('repaint')))
    view=NS(middle=NS(tree=tree),_queue_files_selection_status=lambda:calls.append('status'))
    qt=NS(FocusReason=NS(MouseFocusReason=1,ShortcutFocusReason=2))
    method=extract_method(VIEW, 'ExpandedLauncherView',
                          'clear_middle_row_for_folder_operation',{'Qt':qt})
    method(view,focus_reason=qt.FocusReason.ShortcutFocusReason)
    assert tree.deliberate_blank_selection is True
    assert tree.currentItem() is current
    assert calls==['clear',('focus',2),'sync-directory','repaint','status']
    calls.clear()
    method(view)  # Old tonton click still uses MouseFocusReason.
    assert calls[1]==('focus',1)


def test_insert_is_scoped_to_files_list_and_respects_inline_rename():
    KEY=103
    qt=NS(Key=NS(Key_Insert=KEY,Key_Home=104,Key_Tab=105,
                 Key_Backtab=106,Key_I=107),
          KeyboardModifier=NS(NoModifier=0,ControlModifier=2,ShiftModifier=1),
          FocusReason=NS(ShortcutFocusReason=7))
    qevent=NS(Type=NS(KeyPress=1))
    class QAbstractItemView:
        State=NS(EditingState=9)
    app=NS(activeModalWidget=lambda:None)
    method=extract_method(VIEW,'ExpandedLauncherView','keyboard_files_shortcuts',
                          {'Qt':qt,'QEvent':qevent,'QWidget':Widget,
                           'QApplication':app,'QAbstractItemView':QAbstractItemView})
    launcher=Widget()
    launcher.remote_window=None
    launcher.stop_auto_shuriken_on_list_click=Mock()
    tree=NS(state=lambda:0,_frb_shift_anchor='previous')
    warp=Mock()
    obj=Widget(window=launcher)
    view=NS(isVisible=lambda:True,launcher=launcher,middle=NS(tree=tree),
            _workspace_mode='files',
            _files_keyboard_focus_area=lambda obj:'list',
            clear_middle_row_for_folder_operation=warp)
    event=Event(1,KEY)
    assert method(view,obj,event) and event.accepted
    assert tree._frb_shift_anchor is None
    warp.assert_called_once_with(focus_reason=7)
    launcher.stop_auto_shuriken_on_list_click.assert_called_once_with()

    warp.reset_mock()
    tree.state=lambda:9
    assert method(view,obj,Event(1,KEY)) is False
    warp.assert_not_called()

    tree.state=lambda:0
    view._files_keyboard_focus_area=lambda obj:'main_search'
    assert method(view,obj,Event(1,KEY)) is False
    warp.assert_not_called()

    view._workspace_mode='browser'
    view._files_keyboard_focus_area=lambda obj:'list'
    assert method(view,obj,Event(1,KEY)) is False
    warp.assert_not_called()


def test_launch_owned_and_popup_keyboard_menu_key_are_scoped():
    method=extract_method(VIEW,'ExpandedLauncherView',
                          '_launch_owns_keyboard_source',{'QWidget':Widget})
    launcher=Widget()
    remote=Widget()
    launcher.remote_window=remote
    owner=NS(launcher=launcher)
    root=Widget(window=launcher,parent=launcher)
    child=Widget(parent=root)
    popup=Widget(launcher=launcher)
    popup_child=Widget(parent=popup)
    unrelated=Widget()
    assert method(owner,launcher)
    assert method(owner,remote)
    assert method(owner,root)
    assert method(owner,child)
    assert method(owner,popup)
    assert method(owner,popup_child)
    assert not method(owner,unrelated)


def test_app_level_filter_delegates_finger_zero_before_other_shortcuts():
    # The eventFilter is long, but its first shortcut branch is self-contained
    # and can be exercised with a Qt-free fake owner.
    class FakeSource:
        pass
    types=NS(KeyPress=1,KeyRelease=2,ContextMenu=3)
    qt=NS(Key=NS(Key_Menu=99))
    qevent=NS(Type=types)
    method=extract_method(VIEW, 'ExpandedLauncherView', 'eventFilter',
                          {'QEvent':qevent,'Qt':qt})
    handled=[]
    owner=NS(_launch_owns_keyboard_source=lambda obj:True,
             _finger_zero_keyboard=lambda obj, event:(handled.append(event.key()),
                                                       event.accept(), True)[-1])
    source=FakeSource()
    for kind in (1,2):
        evt=Event(kind,99)
        assert method(owner,source,evt) is True
        assert evt.accepted
    assert handled == [99, 99]


def test_list_insert_and_right_context_routing_is_not_menu_key_alias():
    from test_expanded_keyboard_dispatch_20261024 import instance, Qt
    Qt.Key.Key_Insert=221
    Qt.Key.Key_Menu=222
    Qt.FocusReason.ShortcutFocusReason=12
    launcher=instance()
    launcher.stop_auto_shuriken_on_list_click=Mock()
    view=launcher.expanded_view
    view.clear_middle_row_for_folder_operation=Mock()
    tree=view.middle.tree
    tree._frb_shift_anchor='previous'
    class E:
        def __init__(self,k):self.k=k;self.accepted=False
        def key(self):return self.k
        def modifiers(self):return 0
        def accept(self):self.accepted=True
    inserted=E(Qt.Key.Key_Insert)
    assert launcher.expanded_tree_key(tree,inserted)
    assert inserted.accepted
    view.clear_middle_row_for_folder_operation.assert_called_once_with(focus_reason=12)
    assert tree._frb_shift_anchor is None
    assert launcher.expanded_tree_key(tree,E(Qt.Key.Key_Menu))
    view.clear_middle_row_for_folder_operation.assert_called_once()

    tree.deliberate_blank_selection=True
    view.middle_back_lane=NS(rect=lambda:NS(center=lambda:'center'),
                             mapToGlobal=lambda pt:'folder-anchor')
    view.show_list_background_context=Mock(return_value=True)
    launcher._launch_context_menu=None
    assert launcher.expanded_tree_key(tree,E(Qt.Key.Key_Right))
    view.show_list_background_context.assert_called_once_with('folder-anchor')
    assert view.actions==[]  # No old child-row action executed.

    assert launcher.expanded_tree_key(tree,E(Qt.Key.Key_Enter))
    assert view.actions==[]  # A passive outline is not an Enter target either.


def test_native_keyboard_context_is_consumed_not_translated_to_right():
    assert 'if event.reason() == QContextMenuEvent.Reason.Keyboard:' in VIEW
    assert 'if self._launch_owns_keyboard_source(obj):' in VIEW
    assert 'self.launcher.expanded_tree_key(self.middle.tree, right)' not in VIEW
    assert 'self._right_arrow_for_menu_key()' not in SLASH
    # Mouse right-click stays intact.
    assert 'self.show_lane_new_menu(event.globalPos())' in VIEW
    assert 'view.context_menu(pane, point, global_pos=position)' in APP


def test_launch_owned_native_keyboard_context_event_is_consumed(monkeypatch):
    import sys
    from types import ModuleType
    gui=ModuleType('PySide6.QtGui')
    gui.QContextMenuEvent=NS(Reason=NS(Keyboard=7,Mouse=8))
    pkg=ModuleType('PySide6')
    pkg.QtGui=gui
    monkeypatch.setitem(sys.modules,'PySide6',pkg)
    monkeypatch.setitem(sys.modules,'PySide6.QtGui',gui)
    qt=NS(Key=NS(Key_Menu=99))
    qevent=NS(Type=NS(KeyPress=1,KeyRelease=2,ContextMenu=3))
    method=extract_method(VIEW,'ExpandedLauncherView','eventFilter',
                          {'QEvent':qevent,'Qt':qt})
    toggle=Mock()
    owner=NS(_launch_owns_keyboard_source=lambda obj:True,
             _finger_zero_keyboard=lambda obj, event:False,
             launcher=NS(toggle_slash_exp_shortcut=toggle))
    event=Event(3)
    event.reason=lambda:7
    assert method(owner,object(),event) is True
    assert event.accepted
    toggle.assert_called_once_with()  # Native-only keyboard ContextMenu event.
    owner._finger_menu_context_pending=True  # Already processed Key_Menu press.
    toggle.reset_mock()
    assert method(owner,object(),event) is True
    toggle.assert_not_called()  # No double toggle for one physical press.
