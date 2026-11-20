"""Exp Keyboard Ex floating layout/design contract (portable, no GUI)."""
from types import SimpleNamespace

from launch_appearance import slash_exp_floating_qss, theme_palette
from slash_popup_layout import popup_xy
from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Item


def test_floating_qss_same_house_as_files_list_light_and_dark():
    for theme in ('light', 'dark'):
        colors = theme_palette(theme)
        css = slash_exp_floating_qss(theme, 37)
        assert f'background-color:{colors["panel"]}' in css
        assert f'border:1px solid {colors["panel_border"]}' in css
        assert f'background:{colors["selection"]}' in css
        assert f'color:{colors["text"]}' in css
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
    assert (anchor.x(),anchor.y(),parent_left) == (625,265,365)


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
    assert (anchor.x(),anchor.y(),parent_left)==(269,214,20)


def test_unrelated_exp_current_folder_does_not_change_anchor(nav):
    mod,_ = nav
    source=Item('docs',{'path':'C:/FRB/docs'})
    index=SimpleNamespace(isValid=lambda:True)
    actual=Item('other',{'path':'C:/FRB/other'})
    exp_tree=SimpleNamespace(isVisible=lambda:True,hasFocus=lambda:True,
                             currentIndex=lambda:index)
    panel=SimpleNamespace(tree=exp_tree,model=SimpleNamespace(itemFromIndex=lambda _:actual))
    assert mod.slash_popup_row_anchor(SimpleNamespace(middle=None),panel,source,source) is None
