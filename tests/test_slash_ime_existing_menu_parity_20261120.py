"""Parity contract: / popup uses the same focused-menu IME pipeline as CascadeMenu.

Native Win11 IME conversion still needs an on-device acceptance test; these
checks prevent the missing ImEnabled query and double-frame regressions.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from launch_appearance import files_operation_context_qss
from test_slash_exp_navigation_20261118 import nav, Panel, make_launcher


def test_slash_advertises_ime_to_windows_even_with_menu_focus(nav):
    mod, _ = nav
    # The portable fake exposes only the subset Qt used by existing tests.
    mod.Qt.InputMethodQuery = type('IMEQuery', (), {'ImEnabled': 202})
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([]))
    menu.populate()
    assert menu.inputMethodQuery(mod.Qt.InputMethodQuery.ImEnabled) is True


def test_slash_ime_matches_working_cascade_contract():
    slash = (ROOT / 'src/slash_exp_navigation.py').read_text('utf-8')
    cascade = (ROOT / 'src/app.py').read_text('utf-8')
    assert 'if query == Qt.InputMethodQuery.ImEnabled:' in slash
    assert 'if query == Qt.InputMethodQuery.ImEnabled:' in cascade
    assert 'QApplication.sendEvent(self._search_edit, event)' in slash
    assert 'QApplication.sendEvent(self.filter_edit, event)' in cascade
    # A native popup may reassign the editor's focus after showing. The / menu
    # itself must remain a valid Windows input-method target, like CascadeMenu.
    focus = slash.split('    def _focus_search_for_ime(self):', 1)[1].split('\n    def ', 1)[0]
    assert 'self.setFocus(Qt.FocusReason.OtherFocusReason)' in focus
    assert 'self._search_edit.setFocus(' not in focus


def test_native_action_popup_has_one_frame_not_css_plus_painter():
    qss = files_operation_context_qss('light')
    assert 'QMenu#frbFilesContextMenu {border:0;border-radius:10px;}' in qss
    # The existing Qt.Tool menu still paints a single rounded outline AFTER
    # Qt has rendered QAction foreground; no duplicate custom icon painter.
    app = (ROOT / 'src/app.py').read_text('utf-8')
    section = app.split('class FRBContextMenu(', 1)[1].split('class RemoteFolderCascade(', 1)[0]
    assert 'NoDropShadowWindowHint' in section
    assert 'super().paintEvent(event)' in section
    assert 'drawRoundedRect(' in section


def test_os_ime_preedit_protects_native_menu_enter(nav):
    mod, key = nav
    launcher, _ = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([]))
    menu.populate()
    menu.popup((10, 10))
    editor = menu._search_edit
    editor.ime_composing = True
    class Key:
        def key(self): return key.Key_Return
        def text(self): return ''
        def modifiers(self): return 0
        def accept(self): self.accepted = True
    event = Key()
    menu.keyPressEvent(event)
    assert event.accepted is True
    assert menu.isVisible()
