"""FRB Launch visual palettes.

Only appearance belongs here.  Search, page navigation, and Launch DataJSON
stay unchanged.  Keep the original dark theme as the default.
"""


def normalize_theme(value):
    key = str(value).strip().lower()
    return key if key in THEME_REGISTRY else 'dark'



# Central theme catalog.  Display names, base family, and semantic colors live
# together so a new scheme can be registered without changing the gear menu or
# three-layer widget.  The original compact dark palette is intentionally kept.
THEME_REGISTRY = {
    'light': {
        'label': 'Light（ライト）', 'family': 'light',
        'window': '#edf5f0', 'header': '#dbe7df', 'subheader': '#f8fcfa',
        'panel': '#fcfffd', 'panel_border': '#bbd8c7', 'panel_header': '#eaf6ec',
        'column_header': '#f3faf5', 'workspace_strip': '#f3faf6',
        'text': '#233e32', 'muted_text': '#607a6d', 'hover': '#ecf7f1',
        'selection': '#d7ece1', 'stripe': '#e7f3ed',
        'focus_outline': '#8fc7ab', 'row_separator': '#eaf0eb',
        'root_button_border': '#bbd8c7',
        'history_bg': '#ffffff', 'history_border': '#acc9ba',
        'history_text': '#284338', 'history_selected': '#d6e7f8',
        'history_selected_text': '#1d3b4b', 'history_hover': '#e4eee8',
        'search_bg': '#ffffff', 'search_fg': '#2b433a',
        'search_border': '#8fb29f', 'search_focus': '#6e9f8b',
        # Files List warm operating surface: keep the brown nuance but
        # lighten it toward the original pale tone (trial middle point).
        'files_list_active_bg': '#FCF9F5',
    },
    'dark': {
        'label': 'Dark（ダーク）', 'family': 'dark',
        'window': '#202b29', 'header': '#263532', 'subheader': '#263a35',
        'panel': '#222e2c', 'panel_border': '#4b6660', 'panel_header': '#344a42',
        'column_header': '#394d43', 'workspace_strip': '#2a3b35',
        'text': '#e6f0eb', 'muted_text': '#a2b9ae', 'hover': '#344d47',
        'selection': '#416457', 'stripe': '#32433e',
        'focus_outline': '#86bea7', 'row_separator': '#455851',
        'root_button_border': '#698779',
        'history_bg': '#223043', 'history_border': '#58718c',
        'history_text': '#e8f1fa', 'history_selected': '#365778',
        'history_selected_text': '#ffffff', 'history_hover': '#344b63',
        'search_bg': '#1a2422', 'search_fg': '#e8f2eb',
        'search_border': '#5d7b71', 'search_focus': '#88b4a1',
        # Dark operating surface is approved: DO NOT change its brown.
        'files_list_active_bg': '#463a32',
    },
}


def theme_palette(theme):
    """Shared semantic palette for header, compact view and three-layer UI."""
    return THEME_REGISTRY[normalize_theme(theme)]


def theme_family(theme):
    """Legacy QSS/icon family (light/dark), even for future named schemes."""
    return theme_palette(theme)['family']


def available_themes():
    """Ordered IDs for automatically populated theme menus."""
    return tuple(THEME_REGISTRY)




def bookmark_section_colors(theme):
    """Subtle bookmark section heading colors."""
    if theme_family(theme) == 'light':
        return {
            'background': '#f7faf8',
            'accent': '#c7ded0',
            'divider': '#edf2ee',
            'text': '#527062'
        }
    return {
        'background': '#30443a',
        'accent': '#729e87',
        'divider': '#405a4b',
        'text': '#d7e8dd'
    }



def history_popup_qss(theme, *, frame_name='historyPopup',
                      tree_name='historyChoices', height=31, padding=6,
                      vertical_padding=2, font_size=None):
    """Shared search-history / folder-favorites popup colors.

    The widget names and row geometry may differ, but the background and
    selection colors always come from the *same theme tokens*.
    """
    colors = theme_palette(theme)
    # Only the main-search history explicitly sets Files List typography.
    # Other history/favorites menus keep their established native sizing.
    font_qss = (f'font-family:"Yu Gothic UI";font-size:{font_size}px;'
                if font_size is not None else '')
    height_property = 'min-height' if font_size is not None else 'height'
    return (
        f'QFrame#{frame_name} {{background:{colors["history_bg"]};'
        f'border:1px solid {colors["history_border"]};border-radius:7px;}} '
        f'QTreeWidget#{tree_name} {{background:{colors["history_bg"]};'
        f'color:{colors["history_text"]};border:0;outline:0;{font_qss}}} '
        f'QTreeWidget#{tree_name}::item {{{height_property}:{height}px;'
        f'padding:{vertical_padding}px {padding}px;}} '
        f'QTreeWidget#{tree_name}::item:selected {{background:{colors["history_selected"]};'
        f'color:{colors["history_selected_text"]};}} '
        f'QTreeWidget#{tree_name}::item:hover {{background:{colors["history_hover"]};}}'
    )


def context_menu_spacing_qss(theme):
    """Keep quiet separators readable in both color schemes."""
    color = '#e1e5e2' if theme_family(theme) == 'light' else '#4b5b56'
    return CONTEXT_MENU_SPACING_QSS.replace('#e1e5e2', color)


def launch_action_menu_qss(theme):
    """Item-only styling over a painted rounded Launch action menu window.

    The QMenu background must stay transparent: LaunchActionMenu draws its
    rounded surface on a translucent frameless window. Equal vertical outer
    padding keeps the first row as generously spaced as the last row.
    """
    light = theme_family(theme) == 'light'
    palette = theme_palette(theme)
    fg = '#284238' if light else '#e5ebf3'
    selection = '#d6e7f8' if light else '#304d70'
    disabled = '#8da69a' if light else palette['muted_text']
    separator = '#dce8df' if light else '#4b5b56'
    return (
        # The parent window is transparent and the round panel is painted
        # anti-aliased by LaunchActionMenu. An opaque QSS background would
        # resurrect square native corners on Windows, especially at bottom-right.
        f'QMenu#frbLaunchActionMenu {{ menu-scrollable:1; '
        f'background:transparent; color:{fg}; border:0; '
        f'padding:8px 6px 8px 6px; }} '
        f'QMenu#frbLaunchActionMenu::item {{ padding:7px 18px; margin:0; '
        f'border-radius:4px; background:transparent; color:{fg}; }} '
        f'QMenu#frbLaunchActionMenu::item:selected {{ background:{selection}; '
        f'color:{fg}; }} '
        f'QMenu#frbLaunchActionMenu::item:disabled {{ color:{disabled}; }} '
        f'QMenu#frbLaunchActionMenu::separator {{ background:{separator}; '
        f'height:1px; margin:4px 6px; }} '
    )

# Based on the pastel green/white FRB Studio compact-light appearance.
LIGHT_MAIN_QSS = '''
QWidget { background:#edf5f0; color:#273d36; font-family:"Yu Gothic UI"; font-size:13px; }
QWidget#searchBar { background:transparent; border:0; }
QLineEdit { background:#ffffff; color:#263e35; border:1px solid #bdcfc5;
            border-radius:7px; padding:5px 10px; font-size:15px;
            selection-background-color:#c4ddf6; selection-color:#203d50; }
QLineEdit:focus { border-color:#72a99b; }
QPushButton#themeButton { background:#f8fcf9; color:#2b6257; border:1px solid #a7c8bb;
                          border-radius:6px; font-size:19px; font-weight:bold; padding:0; }
QPushButton#themeButton:hover { background:#deeee5; border-color:#53917e; }
QPushButton#themeButton:pressed { background:#cce4d8; }
QTreeWidget { border:0; outline:0; background:#f8fbf8; color:#253e35;
              alternate-background-color:#f1f7f3; }
QTreeWidget::item { height:35px; padding:0 6px; }
QTreeWidget::item:selected, QTreeWidget::item:selected:!active {
    background:#d6e7f8; color:#1d3b4b; }
QTreeWidget::item:hover:!selected { background:#e4eee8; }
/* The main grid's blue fills and full-row outline are drawn separately.
   History and cascade lists retain their existing styling. */
QTreeWidget#mainLaunchList::item:selected { background:transparent; color:#253e35; }
QTreeWidget#mainLaunchList::item:hover { background:transparent; }
QHeaderView::section { background:#e3eee7; color:#28463b; border:0;
    border-right:1px solid #cbdcd1; border-bottom:1px solid #cbdcd1; padding:3px 8px; }
QHeaderView::section:hover { background:#d2e7db; }
QLabel { color:#607a6d; font-size:11px; }
QPushButton { background:#f8fbf8; color:#235d4c; border:1px solid #bbd1c3;
              border-radius:5px; padding:4px 8px; }
QPushButton:hover { background:#e2f0e8; }
QMenu { background:#ffffff; color:#254138; border:1px solid #c2d4c7; padding:5px; }
QMenu::item { padding:8px 20px; }
QMenu::item:selected { background:#d6e7f8; color:#1d3b4b; }
QAbstractScrollArea::corner { background:#f8fbf8; border:0; }
'''

LIGHT_TABS_QSS = '''
QTabBar { background:transparent; border:none; outline:none; }
QTabBar::tab { background:#e0ebe4; color:#3f6255; border:1px solid #cadbd0;
    border-bottom:2px solid #cadbd0; border-radius:7px; margin-right:5px;
    padding:4px 15px; min-height:23px; }
QTabBar::tab:hover:!selected { background:#d3e8dc; color:#254f40;
    border-color:#a2c5b2; border-bottom-color:#a2c5b2; }
QTabBar::tab:selected { background:#d6e7f8; color:#1c4963;
    border:1px solid #a8c9e7; border-bottom:2px solid #6196c5; }
QTabBar::tab:disabled { background:#edf2ee; color:#9caea4; border-color:#e0e8e2; }
QTabBar::scroller { background:#edf5f0; border:none; }
'''

LIGHT_HISTORY_QSS = '''
QFrame#historyPopup { background:#ffffff; border:1px solid #acc9ba; border-radius:7px; }
QTreeWidget#historyChoices { background:#ffffff; color:#284338; border:0; outline:0;
    font-family:"Yu Gothic UI"; font-size:12px; }
QTreeWidget#historyChoices::item { min-height:29px; padding:3px 7px; }
QTreeWidget#historyChoices::item:selected { background:#d6e7f8; color:#1d3b4b; }
QTreeWidget#historyChoices::item:hover { background:#e4eee8; }
'''

LIGHT_MENU_QSS = '''
QMenu { menu-scrollable:1; background:#ffffff; color:#284238;
        border:1px solid #b6cebe; padding:5px; }
QMenu::item { padding:8px 20px; }
QMenu::item:selected { background:#d6e7f8; color:#1d3b4b; }
QMenu::item:disabled { color:#8da69a; }
QMenu::separator { background:#dce8df; height:1px; margin:4px 6px; }
'''

# Appearance experiment ONLY. To revert Slash-menu colors to the former
# white/blue-green palette without reverting positioning, borders or the
# new light Files List surface, flip this to False. No runtime behavior changes.
SLASH_FILES_LIST_COLOR_TRIAL = False


def slash_exp_floating_colors(theme):
    """Slash-specific color experiment; Files List owns the surface color.

    Other context menus and the dark Files List itself must stay untouched.
    """
    colors = theme_palette(theme)
    dark = normalize_theme(theme) == 'dark'
    if SLASH_FILES_LIST_COLOR_TRIAL:
        # Exactly the same warm operating surface used by Files List.
        return {
            'bg': '#FFFEFD' if not dark else colors['files_list_active_bg'],
            'border': '#AB896C' if dark else '#A98971',
            'divider': '#685449' if dark else '#D4C0AD',
            'hover': '#514238' if dark else '#ECE3D8',
            'search_bg': '#392D27' if dark else '#FCFFFD',
            'search_border': '#91745C' if dark else '#BBD8C7',
        }
    # Original (2026-11-20 18:45) popup colors, retained for easy A/B trial.
    return {
        'bg': '#372c24' if dark else '#f6f2ee',
        'border': '#7a6758' if dark else '#cdb8a6',
        'divider': '#635245' if dark else '#e1d4c9',
        'hover': '#4a3c31' if dark else '#efe7df',
        'search_bg': '#30261f' if dark else '#fbf8f5',
        'search_border': '#7a6758' if dark else '#c5b3a4',
    }


# Gently inset icons relative to Qt's native icon lane.  This is *not*
# menu/item padding: Qt paints QMenu icons in a dedicated subcontrol, and
# scrolling columns use QAbstractItemView's decoration subcontrol.  Keep
# these two paths aligned without custom icon painting or changing other menus.
SLASH_EXP_ICON_INSET_PX = 6
# QMenu uses its own decoration subcontrol; QTreeWidget's item padding
# supplies that same +6px inset instead. Applying BOTH on the tree doubles
# the offset, which caused short/long menu icon misalignment.


def files_operation_menu_colors(theme):
    """Files folder/file operations: blue-white, deliberately NOT the / navigator."""
    if theme_family(theme) == 'light':
        return {
            'bg': '#F7FBFE', 'fg': '#284238', 'border': '#8FAFC5',
            'selection': '#D6E7F8', 'hover': '#E7F1FA',
            'divider': '#CEDFEA', 'search_bg': '#FFFFFF',
            'search_border': '#A6C4D7', 'focus': '#669FC2',
        }
    return {
        'bg': '#243443', 'fg': '#E6F0F5', 'border': '#708DA6',
        'selection': '#365778', 'hover': '#344C65',
        'divider': '#455D70', 'search_bg': '#1C2B38',
        'search_border': '#5D7B94', 'focus': '#91B9D9',
    }


def files_operation_context_qss(theme):
    """Blue-white style shared by native Files Exp/List operation menus."""
    surface = files_operation_menu_colors(theme)
    return (
        f'QMenu {{background:{surface["bg"]};color:{surface["fg"]};'
        f'border:1px solid {surface["border"]};border-radius:10px;}} '
        f'QMenu#frbFilesContextMenu {{border:0;border-radius:10px;}} '
        f'QMenu#frbFilesContextMenu {{padding:9px 5px 5px 9px;}} '
        f'QMenu::item:selected {{background:{surface["selection"]};'
        f'color:{surface["fg"]};border-radius:4px;}} '
        f'QMenu::item:disabled {{color:{theme_palette(theme)["muted_text"]};}} '
    )


def slash_exp_floating_qss(theme, row_height, *, operation=False):
    """Only the Exp Keyboard Ex popup wears Files List's color family.

    The light Files List gets a warmer surface; the dark Files List retains
    its existing #463a32. The popup follows whichever theme is active.
    The border stays independently visible around *all four* edges.
    """
    colors = theme_palette(theme)
    surface = (files_operation_menu_colors(theme) if operation
               else slash_exp_floating_colors(theme))
    fg = surface['fg'] if operation else colors['text']
    active = surface['selection'] if operation else colors['selection']
    focus = surface['focus'] if operation else colors['search_focus']
    bg = surface['bg']
    border = surface['border']
    divider = surface['divider']
    hover = surface['hover']
    search_bg = surface['search_bg']
    search_border = surface['search_border']
    return f"""
        QMenu#slashExpNavigationMenu {{
            menu-scrollable:1; background-color:{bg};color:{fg};
            border:0;border-radius:10px;padding:5px;
            font-family:'Yu Gothic UI';font-size:12px;
        }}
        QMenu#slashExpNavigationMenu::item {{
            height:{int(row_height)}px; padding:0px 9px 0px 15px;
            background:transparent;color:{fg};
        }}
        /* Icon inset only: leave native QAction text and hit testing alone. */
        QMenu#slashExpNavigationMenu::icon {{
            position:relative;left:{SLASH_EXP_ICON_INSET_PX}px;
        }}
        QMenu#slashExpNavigationMenu::item:selected {{
            background:{active};color:{fg};border-radius:4px;
        }}
        QMenu#slashExpNavigationMenu::item:disabled {{color:{colors['muted_text']};}}
        QMenu#slashExpNavigationMenu::separator {{
            background:{divider};height:1px;margin:4px 6px;
        }}
        QWidget#slashExpSearchHolder {{background:transparent;border:0;}}
        QLineEdit#slashExpColumnSearch {{
            background:{search_bg};color:{fg};
            border:1px solid {search_border};border-radius:6px;padding:5px;
            selection-background-color:{active};font-size:12px;
        }}
        QLineEdit#slashExpColumnSearch:focus {{border:1px solid {focus};}}
        QTreeWidget#slashExpFixedScrollList {{
            background:transparent;color:{fg};border:0;outline:0;
            font-family:'Yu Gothic UI';font-size:12px;
        }}
        QTreeWidget#slashExpFixedScrollList::item {{
            /* QTreeWidget already provides its own icon/decorations gutter.
               Unlike QMenu, adding 15px here doubled the icon left inset. */
            min-height:{int(row_height)}px;
            padding:0px 9px 0px {SLASH_EXP_ICON_INSET_PX}px;
        }}
        QTreeWidget#slashExpFixedScrollList::item:selected,
        QTreeWidget#slashExpFixedScrollList::item:selected:!active {{
            background:{active};color:{fg};
        }}
        QTreeWidget#slashExpFixedScrollList::item:hover:!selected {{
            background:{hover};
        }}
    """


LIGHT_CASCADE_TREE_QSS = '''
QTreeWidget#cascadeScrollView { background:#ffffff; color:#284238;
    border:0; outline:0; padding:0; font-family:'Yu Gothic UI'; font-size:13px; }
QTreeWidget#cascadeScrollView::item { height:32px; padding:0 6px; }
QTreeWidget#cascadeScrollView::item:selected,
QTreeWidget#cascadeScrollView::item:selected:!active { background:#d6e7f8; color:#1d3b4b; }
QTreeWidget#cascadeScrollView::item:hover { background:#e4eee8; }
'''

LIGHT_COLUMN_FILTER_QSS = '''
QWidget#columnFilterBar { background:#e8f2eb; border-radius:5px; }
QLineEdit { background:#ffffff; color:#284238; border:1px solid #accdbb;
            border-radius:5px; padding:5px 7px; font-size:13px; }
QLineEdit:focus { border-color:#74ae99; }
QLabel { background:transparent; color:#648071; font-size:11px; }
'''

FRAME_COLORS = {
    'dark': ('#6b756e', '#43524b', '#d0d7cf', '#27362e',
             '#202b29', '#abb5ab', '#101a17', '#f2f5f2'),
    'light': ('#dcebe2', '#c8ddd1', '#a4beaf', '#b3d0bf',
              '#edf5f0', '#9fbaa9', '#d0e0d6', '#244337'),
}


def light_scrollbar_qss(background='#ffffff'):
    """Keep the slim 8px compact scrollbar geometry across both themes."""
    return '''
    QScrollBar:vertical { background:%s; width:8px; margin:0; border:0; }
    QScrollBar:horizontal { background:%s; height:8px; margin:0; border:0; }
    QScrollBar::handle:vertical { background:#a5bfb0; min-height:28px; border-radius:2px; margin:0 2px; }
    QScrollBar::handle:horizontal { background:#a5bfb0; min-width:28px; border-radius:2px; margin:2px 0; }
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background:#76a593; }
    QScrollBar::handle:vertical:pressed, QScrollBar::handle:horizontal:pressed { background:#548a72; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; border:0; background:transparent; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; border:0; background:transparent; }
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical,
    QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal { width:0; height:0; background:transparent; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:transparent; }
    ''' % (background, background)

def scrollbar_for_theme(theme, background):
    """Unified slim scrollbar for three-layer files, bookmarks and popups."""
    style = light_scrollbar_qss(background)
    if theme_family(theme) == 'light':
        return style
    return (style.replace('#a5bfb0', '#607c71')
                 .replace('#76a593', '#8db3a4')
                 .replace('#548a72', '#abcbbd'))


# Shared Files context-menu row spacing and separators only.
# Native QMenu draws the foreground. Never suppress its QAction text/icons,
# and never introduce Exp/List-specific offsets or icon raster resizing.
CONTEXT_MENU_SPACING_QSS = """
QMenu { padding:5px 5px 5px 9px; }
QMenu::item { padding:7px 9px; }
QMenu::separator { height:1px; background:#e1e5e2; margin:5px 3px; }
"""


# The two simple-edit controls must have ONE border/radius contract.  Qt's
# QPlainTextEdit is an abstract scroll area, so target it explicitly rather
# than relying on inherited QLineEdit application styles.
SIMPLE_EDIT_FIELD_QSS = """
QLineEdit#launchSimpleTitle, QPlainTextEdit#launchSimpleDescription {
    background-color:#ffffff; color:#25362d;
    border:1px solid #b9cbc1; border-radius:7px;
    padding:5px 10px;
}
QLineEdit#launchSimpleTitle:focus, QPlainTextEdit#launchSimpleDescription:focus {
    border-color:#48a27b;
}
"""
