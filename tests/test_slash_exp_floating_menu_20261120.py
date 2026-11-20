"""Exp Keyboard Ex floating layout/design contract (portable, no GUI)."""
from types import SimpleNamespace

from launch_appearance import (slash_exp_floating_qss, slash_exp_floating_colors,
                               theme_palette, SLASH_FILES_LIST_COLOR_TRIAL)
from slash_popup_layout import popup_xy
from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Item


def test_floating_qss_same_house_as_files_list_light_and_dark():
    expected = {
        'light': {'bg': '#F7EEE4', 'border': '#BEA084', 'search': '#FFF9F3'},
        'dark': {'bg': '#463a32', 'border': '#AB896C', 'search': '#392D27'},
    }
    for theme in ('light', 'dark'):
        colors = theme_palette(theme)
        css = slash_exp_floating_qss(theme, 37)
        assert SLASH_FILES_LIST_COLOR_TRIAL is True
        assert expected[theme]['bg'] == colors['files_list_active_bg']
        assert f'background-color:{expected[theme]["bg"]}' in css
        assert f'border:1px solid {expected[theme]["border"]}' in css
        assert f'background:{colors["selection"]}' in css
        assert f'color:{colors["text"]}' in css
        assert f'background:{expected[theme]["search"]}' in css
        assert 'border-radius:10px' in css
        assert 'slashExpFixedScrollList' in css
        assert 'slashExpColumnSearch' in css
        assert '37px' in css


def test_below_taskbar_shift_up_without_shrinking_the_menu():
    x,y = popup_xy(450, 720, 300, 420,
                   work_left=0,work_top=0,work_right=1920,work_bottom=1040)
    assert x == 450
    assert y == 610  # 10px work-area margin; menu may extend past Launch.
    assert y + 420 == 1030


def test_horizontal_flip_prefers_left_of_parent_and_preserves_row_y():
    x,y = popup_xy(1510, 230, 380, 280,
                   work_left=0,work_top=0,work_right=1680,work_bottom=980,
                   parent_left=1150)
    assert (x,y) == (770,230)


def test_workarea_guard_on_top_left_bottom_right():
    assert popup_xy(-70, -120, 300, 400,work_left=0,work_top=0,
                    work_right=800,work_bottom=600) == (10,10)
    assert popup_xy(790, 590, 300, 400,work_left=0,work_top=0,
                    work_right=800,work_bottom=600) == (490,190)


def test_all_columns_use_same_files_list_palette(nav):
    mod,_ = nav
    launcher,_ = make_launcher()
    launcher.color_theme = 'dark'
    root=mod.SlashExpMenu(launcher,Panel([Item('child',{'file':True})]))
    root.populate()
    assert root._slash_colors == theme_palette('dark')
    assert root._item_height == 37


def test_visible_list_folder_row_anchors_to_name_column_right(nav):
    mod, _ = nav
    class Pos:
        def __init__(self,x,y): self.x_value=x;self.y_value=y
        def x(self): return self.x_value
        def y(self): return self.y_value
    class Rect:
        def isValid(self): return True
        def top(self): return 65
        def bottom(self): return 98
    class Row:
        def isSelected(self): return True
    selected=Row()
    name_header=SimpleNamespace(sectionViewportPosition=lambda _: 15,
                                sectionSize=lambda _: 260)
    viewport=SimpleNamespace(height=lambda: 550,
                             mapToGlobal=lambda point: Pos(350+point.x(),200+point.y()))
    list_tree=SimpleNamespace(currentItem=lambda: selected,
                              selectedItems=lambda: [selected],
                              property=lambda _:False,
                              visualItemRect=lambda _: Rect(),
                              header=lambda: name_header, viewport=lambda:viewport)
    view=SimpleNamespace(middle=SimpleNamespace(tree=list_tree),
                         row_data=lambda _: {'item_kind':'directory','title':'sub'})
    breadcrumb=object()
    source=Item('sub',{'path':'C:/sub'})
    anchor,parent_left=mod.slash_popup_row_anchor(view,Panel([]),source,breadcrumb)
    assert (anchor.x(),anchor.y(),parent_left) == (438,265,365)


def test_list_file_and_outline_do_not_impersonate_folder_anchor(nav):
    mod,_ = nav
    source=Item('docs',{'path':'C:/docs'})
    empty=SimpleNamespace(middle=SimpleNamespace(tree=None))
    assert mod.slash_popup_row_anchor(empty, Panel([]),source,source) is None


def test_floating_popup_cap_uses_list_height_but_screen_bounds_for_position(nav):
    mod,_=nav
    launcher,_=make_launcher()
    launcher.color_theme = 'light'
    assert mod.popup_exp_navigator(launcher,Panel([Item('file.txt',{'file':True})]),
                                   mod.QPoint(400,760),first_column_width=280,
                                   list_height=430, parent_left=300)
    root=launcher._slash_exp_navigation_menu
    assert root._popup_height == 430
    assert root.maximum_height == 430
    # Popup ends before the available desktop bottom, not at Launch's bottom.
    assert root.pos().y() + root.height() <= 791


def test_visible_exp_current_folder_row_is_symmetric_to_list_parent(nav):
    mod,_ = nav
    class Index:
        def isValid(self): return True
    class Rect:
        def isValid(self): return True
        def top(self): return 94
        def bottom(self): return 124
    class Pos:
        def __init__(self,x,y): self._x=x;self._y=y
        def x(self): return self._x
        def y(self): return self._y
    index=Index()
    source=Item('docs',{'path':'C:/FRB/docs'})
    actual=Item('docs',{'path':'c:/FRB/docs'})
    viewport=SimpleNamespace(height=lambda:600,width=lambda:250,
                             mapToGlobal=lambda point:Pos(20+point.x(),120+point.y()))
    tree=SimpleNamespace(isVisible=lambda:True,hasFocus=lambda:True,
                         currentIndex=lambda:index,visualRect=lambda _:Rect(),
                         viewport=lambda:viewport)
    panel=SimpleNamespace(tree=tree,model=SimpleNamespace(itemFromIndex=lambda _:actual))
    view=SimpleNamespace(middle=SimpleNamespace(tree=None))
    anchor,parent_left=mod.slash_popup_row_anchor(view,panel,source,source)
    assert (anchor.x(),anchor.y(),parent_left)==(102,214,20)


def test_unrelated_exp_current_folder_does_not_change_anchor(nav):
    mod,_ = nav
    source=Item('docs',{'path':'C:/FRB/docs'})
    index=SimpleNamespace(isValid=lambda:True)
    actual=Item('other',{'path':'C:/FRB/other'})
    exp_tree=SimpleNamespace(isVisible=lambda:True,hasFocus=lambda:True,
                             currentIndex=lambda:index)
    panel=SimpleNamespace(tree=exp_tree,model=SimpleNamespace(itemFromIndex=lambda _:actual))
    assert mod.slash_popup_row_anchor(SimpleNamespace(middle=None),panel,source,source) is None


def test_internal_folder_path_must_not_set_menu_x_when_caption_is_short(nav):
    """A long physical path in DataJSON is not the visible row label."""
    mod,_ = nav
    class Row:
        def isSelected(self): return True
        def text(self, column):
            assert column == 0
            return 'docs'  # User sees just this, NOT the long metadata title.
    class Rect:
        def isValid(self): return True
        def top(self): return 40
        def bottom(self): return 65
    selected=Row()
    header=SimpleNamespace(sectionViewportPosition=lambda _: 0, sectionSize=lambda _: 330)
    viewport=SimpleNamespace(height=lambda: 450,
            mapToGlobal=lambda p: mod.QPoint(310+p.x(),130+p.y()))
    list_tree=SimpleNamespace(currentItem=lambda: selected,
            selectedItems=lambda: [selected], property=lambda _: False,
            visualItemRect=lambda _: Rect(), header=lambda: header,
            viewport=lambda: viewport)
    # This title is intentionally much longer than the Name column.
    long_title = 'C:/FRB/some/very/very/very/long/physical/path/docs'
    view=SimpleNamespace(middle=SimpleNamespace(tree=list_tree),
            row_data=lambda _: {'item_kind':'directory', 'title':long_title})
    source=Item('docs',{'path':'C:/FRB/docs'})
    anchor,_=mod.slash_popup_row_anchor(view,Panel([]),source,object())
    # Only icon+caption+14px gap; no needless jump to the Name column edge.
    assert anchor.x() == 310 + 8 + 24 + 4*9 + 14
    assert anchor.y() == 170


def test_exp_nested_folder_position_uses_visual_rect_indent(nav):
    mod,_=nav
    class Rect:
        def isValid(self):return True
        def left(self):return 48
        def top(self):return 45
        def bottom(self):return 70
    source=Item('docs',{'path':'C:/FRB/docs'})
    actual=Item('docs',{'path':'C:/FRB/docs'})
    viewport=SimpleNamespace(height=lambda:500,width=lambda:270,
            mapToGlobal=lambda p:mod.QPoint(20+p.x(),60+p.y()))
    tree=SimpleNamespace(isVisible=lambda:True,hasFocus=lambda:True,
            currentIndex=lambda:SimpleNamespace(isValid=lambda:True),
            visualRect=lambda _:Rect(),viewport=lambda:viewport)
    panel=SimpleNamespace(tree=tree,model=SimpleNamespace(itemFromIndex=lambda _:actual))
    anchor,_=mod.slash_popup_row_anchor(SimpleNamespace(middle=None),panel,source,source)
    assert anchor.x() == 20 + 48 + 8 + 24 + 4*9 + 14
    assert anchor.y() == 105


def test_palette_preview_can_be_switched_back_without_navigation_changes(monkeypatch):
    import launch_appearance as appearance
    assert appearance.theme_palette('dark')['files_list_active_bg']=='#463a32'
    assert appearance.theme_palette('light')['files_list_active_bg']=='#F7EEE4'
    monkeypatch.setattr(appearance,'SLASH_FILES_LIST_COLOR_TRIAL',False)
    assert appearance.slash_exp_floating_colors('light')['bg']=='#f6f2ee'
    assert appearance.slash_exp_floating_colors('dark')['bg']=='#372c24'
    assert 'background-color:#372c24' in appearance.slash_exp_floating_qss('dark',37)
    monkeypatch.setattr(appearance,'SLASH_FILES_LIST_COLOR_TRIAL',True)
    assert appearance.slash_exp_floating_colors('dark')['bg']=='#463a32'


def test_exp_and_embedded_list_share_light_surface_and_preserve_dark():
    from pathlib import Path
    src=Path(__file__).resolve().parents[1]/'src'
    for name in ('expanded_view.py','remote_files_explorer.py'):
        txt=(src/name).read_text(encoding='utf-8')
        assert "operating_bg = colors['files_list_active_bg']" in txt
    assert theme_palette('dark')['files_list_active_bg'] == '#463a32'
