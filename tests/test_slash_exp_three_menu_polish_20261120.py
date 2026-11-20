"""2026-11-20: same navigation gutter, current-folder root, separate blue operations."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from launch_appearance import (files_operation_menu_colors,
                               files_operation_context_qss,
                               slash_exp_floating_qss,
                               SLASH_EXP_ICON_INSET_PX)
from context_menu_presentation import style_context_menu
from test_slash_exp_navigation_20261118 import nav, Item, Panel, make_launcher


def test_one_navigation_icon_inset_not_applied_twice():
    assert SLASH_EXP_ICON_INSET_PX == 6
    for theme in ('light', 'dark'):
        qss = slash_exp_floating_qss(theme, 37)
        assert f'position:relative;left:{SLASH_EXP_ICON_INSET_PX}px;' in qss
        assert f'padding:0px 9px 0px {SLASH_EXP_ICON_INSET_PX}px;' in qss
        assert 'QTreeWidget#slashExpFixedScrollList::icon' not in qss


def test_first_slash_column_provides_real_current_folder_for_context(nav, tmp_path):
    mod, key = nav
    launcher, _ = make_launcher()
    (tmp_path / 'file.md').write_text('ok')
    source = Item('docs', {'path': str(tmp_path), 'pc': False})
    menu = mod.SlashExpMenu(launcher, Panel([]), source_item=source)
    labels = [item.text() for item in menu._items()]
    assert labels == ['（カレントフォルダー）', 'file.md']
    menu.populate()
    first = next(iter(menu._action_items))
    assert menu._action_items[first].data(mod._DATA_ROLE)['current_folder']
    assert first in menu._context_hint_actions
    # Unrooted Exp root must NEVER invent a filesystem current folder.
    unrooted = mod.SlashExpMenu(launcher, Panel([Item('Page', {'virtual': {'kind':'page'}})]))
    assert '（カレントフォルダー）' not in [x.text() for x in unrooted._items()]


def test_operation_menu_is_blue_white_and_not_navigation_surface():
    for theme in ('light', 'dark'):
        operation = files_operation_menu_colors(theme)
        operation_qss = slash_exp_floating_qss(theme, 37, operation=True)
        navigation_qss = slash_exp_floating_qss(theme, 37)
        assert f'background-color:{operation["bg"]}' in operation_qss
        assert f'background:{operation["selection"]}' in operation_qss
        assert operation_qss != navigation_qss
        assert 'QMenu#frbFilesContextMenu {border:0;border-radius:10px;}' in files_operation_context_qss(theme)
        assert 'border-radius:10px' in operation_qss
        assert 'border-radius:10px' in files_operation_context_qss(theme)
    assert files_operation_menu_colors('light')['bg'] == '#F7FBFE'


def test_root_virtual_folder_and_attached_operation_column_are_distinct(nav):
    mod, _ = nav
    launcher, _ = make_launcher()
    folder = {'kind':'folder', 'source':'launch_json',
              'node_id':'folder', 'title':'Docs', 'children':[]}
    source = Item('Docs', {'virtual':folder})
    root = mod.SlashExpMenu(launcher, Panel([]), source_item=source)
    assert [x.text() for x in root._items()] == ['（カレントフォルダー）']
    assert root._slash_frame_border != files_operation_menu_colors('light')['border']
    operation = mod.SlashExpMenu(launcher, Panel([]), root=root,
                                  context_source=type('Source', (), {'actions': lambda self: []})())
    assert operation._slash_frame_border == files_operation_menu_colors('light')['border']
    assert operation._slash_colors['panel'] == files_operation_menu_colors('light')['bg']


def test_native_exp_list_contexts_share_blue_operation_palette():
    class FakeMenu:
        def setStyleSheet(self, qss): self.qss = qss
    a, b = FakeMenu(), FakeMenu()
    style_context_menu(a, 'light')
    style_context_menu(b, 'light')
    assert a.qss == b.qss
    assert 'background:#F7FBFE' in a.qss
    assert 'border-radius:10px' in a.qss
    assert 'QMenu::icon' not in a.qss
    d = FakeMenu()
    style_context_menu(d,'dark')
    assert 'background:#243443' in d.qss


def test_native_context_foreground_painter_contract_kept():
    source=(ROOT/'src/app.py').read_text(encoding='utf-8')
    start=source.index('class FRBContextMenu(')
    end=source.index('class RemoteFolderCascade(', start)
    native=source[start:end]
    # A tiny frame-only paintEvent is now required for a visible rounded
    # border on Windows. Native Qt must still paint all action foreground.
    assert native.count('def paintEvent(') == 1
    assert 'super().paintEvent(event)' in native
    assert 'drawRoundedRect(' in native
    assert 'QStyleOptionMenuItem' not in native
    assert 'drawText(' not in native and 'drawPixmap(' not in native
    assert 'def resizeEvent(' in native  # rounded physical window mask
    assert 'WA_TranslucentBackground' in native
    assert "self.setObjectName('frbFilesContextMenu')" in native
    assert 'return context' in (ROOT/'src/slash_exp_navigation.py').read_text(encoding='utf-8')
