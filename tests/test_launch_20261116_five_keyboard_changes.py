"""2026-11-16: requested five-keyboard-change contract tests (Qt-free).

The source archive is Windows/PySide6-specific.  In this environment we can
exercise the existing Qt-free QAction runner with fake events and check that
its production dispatch sites have been connected to the shared code paths.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

from test_remote_context_wheel_prototype_20261103 import harness

BASE = Path(__file__).resolve().parents[1]
APP = (BASE / 'src' / 'app.py').read_text('utf-8')
VIEW = (BASE / 'src' / 'expanded_view.py').read_text('utf-8')
RUNNER = (BASE / 'src' / 'remote_context_wheel.py').read_text('utf-8')


def method(source, class_name, method_name):
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    func = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    return ast.get_source_segment(source, func)


def test_pad_context_preserves_authored_root_identity_and_child_fallback():
    impl = method(APP, 'Launcher', '_show_remote_target_context_menu')
    assert 'panel.registered_root_identity(item)' in impl
    assert "data.get('studio_identity')" in impl
    assert 'self.show_files_exp_authored_root_menu(path, identity, pos)' in impl
    assert 'self.show_files_exp_folder_menu(path, pos)' in impl
    # Parent/descendant permissions must still be verified by the existing gate.
    assert 'verified_registered_root' in method(APP, 'Launcher', 'show_files_exp_authored_root_menu')
    assert "if studio_properties_item_id and remote_folder_list:" in method(
        APP, 'Launcher', 'show_expanded_background_paste_menu')


def test_pageup_at_first_list_row_ascends_but_other_rows_use_native_qt():
    impl = method(APP, 'Launcher', 'expanded_tree_key')
    assert "key == getattr(Qt.Key, 'Key_PageUp', None) and pane is view.middle" in impl
    assert 'tree_widget.currentItem() is first' in impl
    assert 'view.go_up(keep_middle_focus=True)' in impl
    assert "return False  # Qt's real PageUp scrolling/selection." in impl
    assert 'def go_up(self, *, keep_middle_focus=False):' in VIEW


def test_main_search_down_opens_history_once_then_moves_existing_cursor():
    impl = method(APP, 'Launcher', 'handle_history_event')
    before, after = impl.split('            self.show_history_popup()\n', 1)
    assert 'obj is self.search and not self.history_popup.isVisible()' in before
    assert 'key == Qt.Key.Key_Down' in before
    assert 'self.history_visible_rows()' in after
    assert 'self.history_choices.setCurrentItem(row)' in after


def test_ctrl_g_targets_breadcrumb_saved_folders_and_down_drives_popup():
    dispatch = method(APP, 'Launcher', 'eventFilter')
    handler = method(VIEW, 'ExpandedLauncherView', 'eventFilter')
    assert 'event.key() == Qt.Key.Key_G' in handler
    assert "self._workspace_mode == 'files'" in handler
    assert 'self.favorite_dropdown.setFocus(Qt.FocusReason.ShortcutFocusReason)' in handler
    assert 'self.expanded_view.favorite_dropdown.setFocus(' in dispatch
    assert 'self.favorite_dropdown.setFocusPolicy(Qt.FocusPolicy.ClickFocus)' in VIEW
    assert 'self.toggle_directory_favorites()' in handler
    assert 'move_tree_selection(self.favorite_choices,' in handler
    assert 'self.directory_favorite_clicked(row, 0)' in handler


def test_only_expanded_files_list_right_clicks_menu_enter_stays_unchanged():
    impl = method(APP, 'Launcher', 'expanded_tree_key')
    assert 'if pane is view.middle:' in impl
    assert 'view.context_menu(pane, point, global_pos=position)' in impl
    assert "context._frb_keyboard_opened = True" in impl
    assert "elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):" in impl
    assert 'view.enter_row(pane, item)' in impl
    assert 'view.open_cascade(row, pane.tree, item)' in impl  # other column unchanged
    from expanded_keyboard_model import row_right_action
    assert row_right_action('directory', True) == 'context_menu'
    assert row_right_action('directory', False) == 'context_menu'


def test_keyboard_opened_menu_uses_one_real_runner_for_arrows_and_enter(harness):
    mod = harness.module
    mod.QEvent.Type.KeyPress = 'keyboard'
    mod.Qt.KeyboardModifier = NS(NoModifier=0)
    mod.Qt.Key = NS(Key_Up=1, Key_Down=2, Key_Left=3, Key_Right=4,
                    Key_Return=5, Key_Enter=6, Key_Escape=7)

    a = harness.module.selectable_actions  # verify we test production runner
    assert callable(a)
    from test_remote_context_wheel_prototype_20261103 import FakeAction, FakeMenu
    leaf = FakeAction('ファイル新規')
    submenu = FakeMenu(leaf)
    submenu.visible = False
    copy = FakeAction('コピー')
    create = FakeAction('新規作成', submenu=submenu)
    menu, controller = harness.new_menu(copy, create)
    menu._frb_keyboard_opened = True
    harness.drain()

    class Keyboard:
        def __init__(self, key):
            self.key_value = key
            self.accepted = False
        def type(self): return 'keyboard'
        def modifiers(self): return 0
        def key(self): return self.key_value
        def accept(self): self.accepted = True

    def key(name):
        e = Keyboard(getattr(mod.Qt.Key, 'Key_' + name))
        assert controller.eventFilter(menu, e) is True
        assert e.accepted

    key('Down')
    assert menu.activeAction() is create
    key('Right')
    harness.drain()
    assert submenu.isVisible() and submenu.activeAction() is leaf
    key('Left')
    assert not submenu.isVisible()
    key('Up')
    assert menu.activeAction() is copy
    key('Enter')
    assert not menu.isVisible()
    harness.drain()
    assert copy.trigger_calls == 1
    assert create.trigger_calls == 0
    assert leaf.trigger_calls == 0
