"""2026-11-20: last-mile / menu appearance and Japanese IME contracts."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from test_slash_exp_navigation_20261118 import nav, Item, Panel, make_launcher
from launch_appearance import files_operation_menu_colors


def test_operations_have_same_width_as_existing_files_contexts(nav):
    mod, _ = nav
    assert mod.SLASH_OPERATION_WIDTH == 225
    launcher, _ = make_launcher()
    class Command:
        def text(self): return '名前の変更'
        def isSeparator(self): return False
        def isVisible(self): return True
        def icon(self): return type('I', (), {'isNull': lambda self: True})()
        def toolTip(self): return '名前の変更'
        def isEnabled(self): return True
        def menu(self): return None
    source = type('Source', (), {'actions': lambda self: [Command()]})()
    menu = mod.SlashExpMenu(launcher, Panel([]), context_source=source)
    menu.populate()
    assert menu.fixed_width == 225


def test_navigation_width_still_independent_of_operation_width(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    source = Item('folder', {'path': None, 'pc': False})
    menu = mod.SlashExpMenu(launcher, Panel([]), source_item=source)
    menu._pick_column_width(['short'])
    assert menu.fixed_width == mod.SLASH_STANDARD_WIDTH


def test_current_folder_paint_has_subtle_background_in_both_renderers():
    s = (ROOT / 'src/slash_exp_navigation.py').read_text(encoding='utf-8')
    assert "'#FAF7F4'" in s
    assert 'current_folder = isinstance(details, dict)' in s
    assert "row.setBackground(0, color)" in s
    assert "row.setBackground(1, color)" in s
    # Original navigation and blue-white operation menu palettes remain.
    assert files_operation_menu_colors('light')['bg'] == '#F7FBFE'


def test_native_op_menu_frame_after_qt_paint_not_icon_overpaint():
    s = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    part = s.split('class FRBContextMenu(', 1)[1].split('class RemoteFolderCascade(', 1)[0]
    paint = part.split('    def paintEvent(self, event):', 1)[1].split('    def keyPressEvent(', 1)[0]
    assert 'super().paintEvent(event)' in paint
    assert 'drawRoundedRect' in paint
    assert 'QStyleOptionMenuItem' not in paint
    assert 'drawText(' not in paint
    assert 'NoDropShadowWindowHint' in part


def test_ime_has_a_real_focused_search_editor_and_keeps_navigation():
    s = (ROOT / 'src/slash_exp_navigation.py').read_text(encoding='utf-8')
    assert 'class SlashSearchEdit(QLineEdit)' in s
    assert 'self.ime_composing = bool(event.preeditString())' in s
    assert "getattr(self._search_edit, 'ime_composing', False)" in s
    assert 'menu._focus_search_for_ime()' in s
    assert 'submenu._focus_search_for_ime()' in s
    assert 'parent._focus_search_for_ime()' in s
    assert 'QTimer.singleShot(0, lambda m=menu: m._focus_search_for_ime())' in s


def test_japanese_preedit_holds_enter_and_escape_for_ime(nav, monkeypatch):
    mod, key = nav
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([]))
    menu.populate()
    menu.popup((10, 10))
    # The lightweight Qt fake has no native QLineEdit inputMethodEvent;
    # emulate it only to test the application's composition boundary.
    editor = mod.SlashSearchEdit()
    monkeypatch.setattr(mod.SlashSearchEdit.__mro__[1], 'inputMethodEvent',
                        lambda self, event: None, raising=False)
    event = type('IME', (), {'preeditString': lambda self: '変換中'})()
    editor.inputMethodEvent(event)
    menu._search_edit = editor
    class KeyEvent:
        def __init__(self, k): self.k = k
        def type(self): return 1
        def key(self): return self.k
        def text(self): return ''
        def modifiers(self): return 0
        def accept(self): self.accepted = True
        def isAccepted(self): return getattr(self, 'accepted', False)
    # In the fake Qt event filter, False means the native QLineEdit/IME owns it.
    assert menu.eventFilter(editor, KeyEvent(key.Key_Return)) is False
    assert menu.eventFilter(editor, KeyEvent(key.Key_Escape)) is False
    assert menu.isVisible()
    editor.inputMethodEvent(type('Commit', (), {'preeditString': lambda self: ''})())
    assert not editor.ime_composing
    assert menu.eventFilter(editor, KeyEvent(key.Key_Escape)) is True
    assert not menu.isVisible()
