"""Keyboard-first / navigator projected from the *existing* Files Exp tree.

Unlike ordinary Exp, this temporary menu uses Right only to traverse
branches or open an existing context menu. Enter on a physical/virtual folder
shows that folder in Files List, while Enter on a file executes its usual
Launch action. No secondary store or filesystem mutation is introduced.
"""

import os
import unicodedata
import logging

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QKeyEvent, QPainter, QPainterPath, QPixmap, QStandardItem
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout,
                               QHeaderView, QLineEdit, QMenu, QTreeWidget,
                               QTreeWidgetItem, QWidget, QWidgetAction)

from folder_sort_preferences import load_directory_sort
from middle_folder_filter import SORT_LABELS
from folder_popup_sort import sort_physical_popup_records
from launch_virtual_tree import virtual_item_identity
from launch_appearance import (theme_palette, slash_exp_floating_qss,
                               slash_exp_floating_colors,
                               files_operation_menu_colors)
from slash_popup_layout import popup_xy
import windows


def _trace_current_folder_enter(stage, launcher, menu=None, *, ticket=None, result=None):
    """Diagnostic ONLY: show Qt.Tool depth versus Win32 foreground at Enter.

    No paths, typed text, or action payloads are recorded. This function never
    changes focus or the command result, and failures cannot block navigation.
    """
    try:
        logger = logging.getLogger('frb.launch.diagnostics')
        if not logger.isEnabledFor(logging.INFO):
            return
        launch_hwnd = int(launcher.winId())
        menu_hwnd = None
        root_hwnd = None
        depth = 0
        chain_hwnds = []
        if menu is not None:
            # Query the menu HWND only while it is still visible. Calling
            # winId() on a closed widget could create a fresh native window.
            if menu.isVisible():
                menu_hwnd = int(menu.winId())
            root = getattr(menu, 'root_menu', None)
            if root is not None and root.isVisible():
                root_hwnd = int(root.winId())
            current = menu
            while isinstance(current, SlashExpMenu):
                depth += 1
                if current.isVisible():
                    chain_hwnds.append(int(current.winId()))
                current = current.parentWidget()
        front = int(windows.foreground()) if windows.IS_WINDOWS else None
        tick = windows.last_user_input_tick() if windows.IS_WINDOWS else None
        saved_tick = ticket[1] if isinstance(ticket, tuple) and len(ticket) >= 2 else None
        logger.info(
            'SLASH_ENTER_TRACE stage=%s depth=%s menu_hwnd=%s root_hwnd=%s '
            'chain_hwnds=%s launcher_hwnd=%s foreground_hwnd=%s '
            'foreground_in_chain=%s input_tick=%s saved_tick=%s '
            'ticket=%s restored=%s',
            stage, depth, menu_hwnd, root_hwnd, chain_hwnds, launch_hwnd,
            front, front in chain_hwnds, tick, saved_tick,
            ticket is not None, result)
    except Exception:
        # Logging is nonintrusive even when a Qt.Tool is disappearing.
        pass


_DATA_ROLE = Qt.ItemDataRole.UserRole + 1
_LOADED_ROLE = Qt.ItemDataRole.UserRole + 2

# Two predictable column widths: compact ordinary menus and readable files
# lists. Both are independent of the number of rows / scrollbar visibility.
# Reserve a dedicated right-hand chevron lane in either mode.
SLASH_STANDARD_WIDTH = 300
SLASH_LONG_WIDTH = 300
SLASH_LONG_TEXT_THRESHOLD = 212
# Existing Files Exp/List action menus are sized to 218–225px.
# Keep the Keyboard Ex *operation* column in that same range, independent of
# the wider exploration columns (which follow Names and folder captions).
SLASH_OPERATION_WIDTH = 225
# Files List's Name section has no scroll tree, chevron and native-menu frame.
# One modest gutter correction recovers about the same visible filename span.
SLASH_FIRST_COLUMN_CHROME_PX = 44

# A floating Keyboard Ex column must never occupy more than this share of
# the Launch window, even when Files List is unusually tall.
SLASH_LAUNCH_HEIGHT_RATIO = 0.75


def slash_popup_height_budget(list_height, launch_height, screen_height):
    """Qt-free menu size policy; the smallest height limit always wins."""
    return max(1, min(int(list_height),
                      max(1, int(int(launch_height) * SLASH_LAUNCH_HEIGHT_RATIO)),
                      int(screen_height)))


def slash_menu_page_target(current, visible_count, viewport_height, row_height,
                           direction):
    """Compute a stable index for PageUp/Down in a filtered scroll column."""
    if visible_count <= 0:
        return None
    page_rows = max(1, int(viewport_height) // max(1, int(row_height)) - 1)
    start = int(current) if 0 <= int(current) < visible_count else (0 if direction < 0 else -1)
    return max(0, min(visible_count - 1, start + (-page_rows if direction < 0 else page_rows)))

# Files List's 三 button is the ONLY density authority. Menu row height is
# never derived from the *Launch window height* (which formerly changed the
# QMenu's native item distribution on a small Launch window).
SLASH_MENU_ROWS = {'compact': 27, 'normal': 37}

def slash_source_from_search_result(launcher, view, panel):
    """Keyboard EX starts from the *selected search folder*, never a fake path.

    Search Location has no breadcrumb ancestry. Resolve only the selected
    folder's actual JSON identity or indexed physical path. An invalid match
    returns None instead of browsing the folder that happened to be open.
    """
    tree = getattr(getattr(view, 'middle', None), 'tree', None)
    if tree is None:
        return None
    item = tree.currentItem()
    row = view.row_data(item) if item is not None else None
    if (not isinstance(row, dict) or not row.get('_main_search_result') or
            row.get('item_kind') not in ('category', 'directory')):
        return None
    page_id, item_id = row.get('page_id'), row.get('item_id')
    if (page_id and item_id and not row.get('_file')):
        from launch_virtual_tree import virtual_lookup_node
        node = virtual_lookup_node(launcher.pages, launcher.authored_items,
            page_id, item_id, (launcher.data or {}).get('items', ()))
        if not isinstance(node, dict) or node.get('kind') == 'file':
            return None
        source = QStandardItem(QIcon(), str(node.get('title') or row.get('title', '')))
        source.setData({'virtual': node, 'pc': False, 'path': None}, _DATA_ROLE)
        source.setData(True, _LOADED_ROLE)
        return source
    path = row.get('_file')
    if not isinstance(path, str) or not os.path.isdir(path):
        return None
    source = QStandardItem(QIcon(), row.get('title') or os.path.basename(path))
    source.setData({'path': path, 'pc': False, 'slash_transient': True}, _DATA_ROLE)
    source.setData(False, _LOADED_ROLE)  # Populate its real children lazily.
    return source


def slash_source_from_breadcrumb(launcher, view, panel):
    """Resolve the / starting directory from the *displayed logical crumb*.

    Exp/List selection and keyboard focus are deliberately irrelevant.  The
    breadcrumb owns the current place; this builds a read-only snapshot for
    the existing SlashExpMenu without adding/expanding an Exp model root.
    Returns None for an absent/stale location, NEVER the registered-root list.
    """
    bar = getattr(view, 'address_bar', None)
    segments = getattr(bar, '_segments', ()) if bar is not None else ()
    target = segments[-1][1] if segments else None
    if isinstance(target, tuple) and target and target[0] == 'virtual':
        node = getattr(view, '_virtual_directory_node', None)
        if (not isinstance(node, dict) or node.get('source') != 'launch_json'
                or node.get('kind') == 'file' or len(target) != 3
                or str(node.get('page_id') or '') != str(target[1])
                or str(node.get('item_id') or '') != str(target[2])):
            return None
        # A detached source preserves JSON children, including runnable leaves.
        source = QStandardItem(QIcon(), str(node.get('title') or ''))
        source.setData({'virtual': node, 'pc': False, 'path': None}, _DATA_ROLE)
        source.setData(True, _LOADED_ROLE)
        return source

    directory = (target[1] if isinstance(target, tuple)
                 and len(target) == 2 and target[0] == 'physical'
                 else target if isinstance(target, str) else None)
    if directory:
        # Reject a stale breadcrumb instead of silently using a different
        # highlighted Exp/List row. Compare Windows paths case-insensitively.
        import ntpath
        current = getattr(view, 'current_directory', lambda: None)()
        if (not current or ntpath.normcase(ntpath.normpath(str(current)))
                != ntpath.normcase(ntpath.normpath(str(directory)))
                or not os.path.isdir(str(directory))):
            return None
        source = QStandardItem(QIcon(), os.path.basename(str(directory).rstrip('\\/'))
                               or str(directory))
        source.setData({'path': str(directory), 'pc': False,
                        'slash_transient': True}, _DATA_ROLE)
        source.setData(True, _LOADED_ROLE)
        return source

    # PC is the only non-directory breadcrumb: its current List shows drives
    # but it has no physical path or JSON node. Read the PC navigation state,
    # never a stale selection in Exp or List.
    current_row = (view.path[-1] if getattr(view, 'path', None) else None)
    if (not segments and isinstance(current_row, dict)
            and current_row.get('_system_drives_root')):
        root = panel.model.invisibleRootItem()
        for pos in range(root.rowCount()):
            item = root.child(pos)
            info = item.data(_DATA_ROLE) if item is not None else None
            if isinstance(info, dict) and info.get('pc'):
                return item
    return None


def slash_source_with_filled_list_folder(launcher, view, breadcrumb_source):
    """Optionally descend ONE level from the breadcrumb's logical location.

    The green *filled* Files List current folder is an explicit target;
    a remembered outline, a file, or an inactive List is not.  Never infer a
    directory from the Exp selection, the focus widget, or an unrelated row.
    The selected folder must be a direct logical child of the breadcrumb.
    """
    if breadcrumb_source is None:
        return None
    tree = getattr(getattr(view, 'middle', None), 'tree', None)
    if (tree is None or getattr(tree, 'deliberate_blank_selection', False)
            or tree.property('remoteInactive') is True):
        return breadcrumb_source
    selected = tree.selectedItems()
    if len(selected) != 1 or selected[0] is not tree.currentItem():
        return breadcrumb_source
    item = selected[0]
    if not item.isSelected():
        return breadcrumb_source
    row = view.row_data(item)
    if not isinstance(row, dict):
        return breadcrumb_source

    # Launch JSON folders belong to the logical breadcrumb tree.  Keep the
    # page/item identity, including a linked-directory mount and its aliases.
    node = row.get('_launch_virtual_node')
    parent_node = getattr(view, '_virtual_directory_node', None)
    if isinstance(node, dict) and isinstance(parent_node, dict):
        if node.get('kind') == 'file' or not any(
                child.get('node_id') == node.get('node_id')
                for child in parent_node.get('children', ())):
            return breadcrumb_source
        linked_path = None
        if node.get('kind') == 'linked_directory':
            raw = (node.get('row') or {}).get('launch_browse_target')
            if raw:
                linked_path = launcher.expander().expand(raw)
        source = QStandardItem(launcher.row_icon(row), str(node.get('title') or ''))
        source.setData({'virtual': node, 'pc': False, 'path': None,
                        'linked_path': linked_path}, _DATA_ROLE)
        source.setData(True, _LOADED_ROLE)
        return source

    if row.get('item_kind') != 'directory':
        return breadcrumb_source  # File / URL / action; never descend.
    raw = row.get('launch_browse_target')
    if not raw:
        return breadcrumb_source
    directory = launcher.expander().expand(raw)
    if not directory or not os.path.isdir(directory):
        return breadcrumb_source
    parent_directory = view.current_directory()
    import ntpath
    if parent_directory:
        # Prevent a stale or unrelated selected row becoming another god.
        if (ntpath.normcase(ntpath.normpath(ntpath.dirname(directory)))
                != ntpath.normcase(ntpath.normpath(parent_directory))):
            return breadcrumb_source
    elif not ((breadcrumb_source.data(_DATA_ROLE) or {}).get('pc')
              and row.get('_system_drive')):
        return breadcrumb_source
    source = QStandardItem(launcher.row_icon(row),
                           str(row.get('title') or os.path.basename(directory)))
    source.setData({'path': directory, 'pc': False, 'slash_transient': True,
                    'slash_mount_origin': getattr(view, '_filesystem_entry_origin', None)},
                   _DATA_ROLE)
    source.setData(True, _LOADED_ROLE)
    return source


def _approx_text_width(widget, text):
    """Best-effort text width for popup anchoring in both GUI and tests."""
    metrics = getattr(widget, 'fontMetrics', lambda: None)()
    if metrics is not None:
        advance = getattr(metrics, 'horizontalAdvance', None)
        if callable(advance):
            try:
                return max(0, int(advance(str(text or ''))))
            except Exception:
                pass
    # Portable fallback for test doubles: close enough for geometry policy.
    return max(24, min(260, len(str(text or '')) * 9))


def _row_text_anchor_local_x(widget, *, cell_left, cell_right, label,
                             icon_lane=24, left_padding=8, gap=28):
    """Anchor near the folder caption, not at the far edge of the whole cell."""
    text_width = _approx_text_width(widget, label)
    preferred = int(cell_left) + int(left_padding) + int(icon_lane) + text_width + int(gap)
    max_x = max(int(cell_left) + int(left_padding) + int(icon_lane), int(cell_right) - 8)
    return max(int(cell_left) + int(left_padding) + int(icon_lane), min(preferred, max_x))


def slash_popup_row_anchor(view, panel, source_item, breadcrumb_source):
    """Display anchor only; never re-decide the breadcrumb exploration path.

    Return (global top-right-ish of parent folder caption, global parent-left),
    or None if the actual parent is not shown. List filled folder takes priority
    when it extended the logical breadcrumb. Otherwise an active Exp current
    folder may anchor the popup; files/outline rows never masquerade as parent.
    """
    info = source_item.data(_DATA_ROLE) if source_item is not None else None
    if not isinstance(info, dict):
        return None
    middle = getattr(view, 'middle', None)
    list_tree = getattr(middle, 'tree', None)
    if source_item is not breadcrumb_source and list_tree is not None:
        item = list_tree.currentItem()
        if (item is not None and item.isSelected()
                and list_tree.selectedItems() == [item]
                and list_tree.property('remoteInactive') is not True):
            row = view.row_data(item)
            if isinstance(row, dict) and (row.get('item_kind') == 'directory'
                    or isinstance(row.get('_launch_virtual_node'), dict)
                    and row['_launch_virtual_node'].get('kind') != 'file'):
                rect = list_tree.visualItemRect(item)
                if (rect.isValid() and rect.top() < list_tree.viewport().height()
                        and rect.bottom() >= 0):
                    header = list_tree.header()
                    left_x = header.sectionViewportPosition(0)
                    right_x = left_x + header.sectionSize(0)
                    # Use the VISIBLE cell text, not DataJSON's title:
                    # registered/physical folders may hold a much longer
                    # underlying path while showing only a short caption.
                    # The latter alone controls where the popup should float.
                    display_name = item.text(0) if hasattr(item, 'text') else None
                    anchor_x = _row_text_anchor_local_x(
                        list_tree, cell_left=left_x, cell_right=right_x,
                        label=str(display_name or row.get('title') or ''))
                    viewport = list_tree.viewport()
                    return (viewport.mapToGlobal(QPoint(anchor_x, rect.top())),
                            viewport.mapToGlobal(QPoint(left_x, 0)).x())

    exp_tree = getattr(panel, 'tree', None)
    if (exp_tree is None or not exp_tree.isVisible()
            or not exp_tree.hasFocus()):
        return None
    index = exp_tree.currentIndex()
    if not index.isValid():
        return None
    selected = panel.model.itemFromIndex(index)
    selected_info = selected.data(_DATA_ROLE) if selected is not None else None
    if not isinstance(selected_info, dict):
        return None
    actual_node = selected_info.get('virtual')
    expected_node = info.get('virtual')
    if isinstance(expected_node, dict):
        if (not isinstance(actual_node, dict)
                or expected_node.get('node_id') != actual_node.get('node_id')):
            return None
    else:
        actual_path, expected_path = selected_info.get('path'), info.get('path')
        if not actual_path or not expected_path:
            return None
        import ntpath
        if (ntpath.normcase(ntpath.normpath(str(actual_path))) !=
                ntpath.normcase(ntpath.normpath(str(expected_path)))):
            return None
    rect = exp_tree.visualRect(index)
    viewport = exp_tree.viewport()
    if (not rect.isValid() or rect.top() >= viewport.height()
            or rect.bottom() < 0):
        return None
    label = selected.text() if hasattr(selected, 'text') else str(info.get('path') or '')
    # The Exp item may be nested: visualRect's left is the real indented
    # caption/icon lane. The old hardcoded 0 pulled child menus away from it.
    row_left = rect.left() if hasattr(rect, 'left') else 0
    anchor_x = _row_text_anchor_local_x(exp_tree, cell_left=row_left,
                                        cell_right=viewport.width() - 1,
                                        label=label)
    return (viewport.mapToGlobal(QPoint(anchor_x, rect.top())),
            viewport.mapToGlobal(QPoint(0, 0)).x())


def slash_menu_row_height(launcher):
    view = getattr(launcher, 'expanded_view', None)
    mode = getattr(view, 'row_density', None)
    if mode not in SLASH_MENU_ROWS:
        settings = getattr(launcher, 'settings', None)
        mode = settings.value('expanded_row_density', 'normal') if settings else 'normal'
    return SLASH_MENU_ROWS.get(str(mode), SLASH_MENU_ROWS['normal'])


def slash_screen_height():
    """Monitor geometry, not Launch geometry, determines popup scroll bounds."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return 660
    geometry = screen.availableGeometry()
    height = getattr(geometry, 'height', None)
    return max(240, int(height()) - 40) if callable(height) else 660


def is_slash_shortcut(key, text, modifiers):
    """Only a plain / (including a shifted-layout slash) invokes the mode."""
    return (modifiers in (Qt.KeyboardModifier.NoModifier,
                          Qt.KeyboardModifier.ShiftModifier)
            and (text == '/' or (key == Qt.Key.Key_Slash and not text)))


def leading_page_emoji(label):
    """Separate the authored Page emoji from its caption for the icon lane.

    Files Exp keeps the emoji in the Page title and uses a null QIcon.
    The / menu uses a real icon-sized pixmap instead, so authored icons and
    physical folder/file icons share the same left edge. Ordinary iconless
    names remain left-aligned without a fabricated folder symbol.
    """
    label = str(label)
    if not label:
        return '', label
    first = ord(label[0])
    if not (first >= 0x1F000 or (first >= 0x2600 and
                                    unicodedata.category(label[0]) == 'So')):
        return '', label
    end = 0
    for char in label:
        number = ord(char)
        if (number >= 0x1F000 or number in (0x200D, 0xFE0F, 0xFE0E, 0x20E3)
                or (number >= 0x2600 and unicodedata.category(char) == 'So')):
            end += len(char)
        else:
            break
    return label[:end], label[end:].lstrip() or label


def page_emoji_icon(glyph):
    """Paint a Page's configured emoji in the same 20px lane as QIcons."""
    pix = QPixmap(40, 40)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(QFont('Segoe UI Emoji', 11))
    painter.drawText(QRect(0, 0, 20, 20), Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    return QIcon(pix)


class SlashSearchEdit(QLineEdit):
    """Real, focused IME client for Japanese composition in a Slash column.

    Synthesizing key events into an unfocused QLineEdit only types ASCII: a
    Windows IME needs the *focused* editor to own the actual input context.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ime_composing = False
        if hasattr(self, 'setAttribute'):
            self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)

    def inputMethodEvent(self, event):
        # While composing, Enter/Escape/arrows belong to the Japanese IME,
        # not to the folder navigator. Committed characters still filter rows.
        self.ime_composing = bool(event.preeditString())
        super().inputMethodEvent(event)


class SlashExpMenu(QMenu):
    """Exp hierarchy as native context-menu columns, with arrow-only traversal."""

    def __init__(self, launcher, panel, *, root=None, source_item=None, parent=None,
                 context_source=None):
        super().__init__(parent)
        self.launcher = launcher
        self.panel = panel
        self.root_menu = root if root is not None else self
        self.source_item = source_item
        # The original Exp/List context-menu object owns all command callbacks.
        # Render its QAction objects in another SlashExpMenu column instead of
        # opening FRBContextMenu (a Qt.Tool window) inside a Qt.Popup cascade.
        self._context_source = context_source
        self._full_text = {}
        self._display_text = {}  # untruncated, with emoji separated into icon
        self._iconless_actions = set()
        self._context_hint_actions = set()  # The current-folder row has a Right action.
        self._action_items = {}
        self._submenus = {}
        self._populated = False
        self._row_cache = None
        self._search_action = None
        self._search_edit = None
        self._context_menus = {}
        self._fixed_popup_pos = None
        self._restore_position_queued = False
        # Native QMenu scroll arrows move the popup itself on Windows; that
        # conflicts with the location lock and can leave active rows off-screen.
        # Oversized columns instead use a genuine scrolling item viewport.
        self._scroll_tree = None
        self._scroll_action = None
        self._scroll_items = {}
        self._scroll_rows = {}
        self._scroll_selected_action = None
        # The root column can mirror Files List's resizable Name section.
        # Descendant/context columns retain independent width selection.
        self._exact_first_column_width = None
        self._max_first_column_width = None  # Legacy cap for standalone menus.
        self.setObjectName('slashExpNavigationMenu')
        self.setToolTipsVisible(True)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        # Final width is selected once from this column's contents BEFORE it
        # is shown, avoiding any width changes while Up/Down scrolls.
        self.setFixedWidth(SLASH_STANDARD_WIDTH)
        # Use the SAME row density as Files List, regardless of Launch height.
        # Scroll overflow follows screen size, not a resized Launch window.
        self._item_height = slash_menu_row_height(launcher)
        self._popup_height = slash_screen_height()
        # The first column receives Files List's visible vertical bounds at
        # popup time. Descendants inherit that same bounded navigation area.
        self._list_vertical_bounds = None
        self.setMaximumHeight(self._popup_height)
        # Only the Slash popup is themed as a floating Files List. Generic
        # context menus remain untouched.  Transparency plus a rounded mask
        # prevents the native Windows popup rectangle showing in the corners.
        theme = getattr(launcher, 'color_theme', 'light')
        self._current_folder_bg = ('#FAF7F4' if theme_palette(theme)['family'] == 'light'
                                   else '#41362F')
        if self._context_source is not None:
            operation_colors = files_operation_menu_colors(theme)
            # The iconless-action painter also needs the operation surface;
            # otherwise it paints green List rectangles inside the blue menu.
            self._slash_colors = dict(theme_palette(theme),
                panel=operation_colors['bg'],
                selection=operation_colors['selection'],
                text=operation_colors['fg'])
            self._slash_frame_border = operation_colors['border']
        else:
            self._slash_colors = theme_palette(theme)
            self._slash_frame_border = slash_exp_floating_colors(theme)['border']
        # Windows IME requires the owning menu window to become active.
        # The Windows comparison trace (2026-11-20) confirmed that Qt.Popup
        # never received composition while activated Qt.Tool did.  Tool is
        # now the normal mode for every column, not a diagnostic-only flag.
        self.setWindowFlags(Qt.WindowType.Tool |
                            Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        # Explicitly disable the native popup shadow so the frame is the
        # only visible boundary. Older Qt stubs may lack this Windows hint.
        no_shadow = getattr(Qt.WindowType, 'NoDropShadowWindowHint', None)
        if no_shadow is not None:
            self.setWindowFlag(no_shadow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(slash_exp_floating_qss(
            theme, self._item_height, operation=self._context_source is not None))
        # QMenu still owns its ordinary QAction/item behavior; a dedicated
        # root-session guard restores outside-click dismissal for Qt.Tool.
        self.aboutToShow.connect(self.populate)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # A CSS radius alone sometimes leaves a square native popup backing
        # window on Windows.  Mask the real window outline to rounded corners.
        if self.width() >= 20 and self.height() >= 20:
            from PySide6.QtCore import QRectF
            from PySide6.QtGui import QRegion
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect().adjusted(0, 0, -1, -1)),
                                10.0, 10.0)
            self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _draw_floating_frame(self, painter):
        """Draw the actual popup border; do not rely on native drop shadow.

        Keep every edge well *inside* the rounded native-mask polygon.
        An outline touching the outermost right/bottom pixel is clipped by
        QRegion's integer rasterization on Windows at some DPI scales.
        This helper is called by the ONE effective paintEvent, including when
        its children are rendered in the fixed scrolling viewport.
        """
        if self.width() < 20 or self.height() < 20:
            return
        from PySide6.QtCore import QRectF
        painter.setPen(QColor(self._slash_frame_border))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = 2.5
        painter.drawRoundedRect(
            QRectF(inset, inset,
                   float(self.width()) - 2.0 * inset,
                   float(self.height()) - 2.0 * inset),
            8.0, 8.0)

    def _inherit_list_vertical_bounds(self):
        """Keep cascade columns inside the same List vertical area."""
        bounds = self.root_menu._list_vertical_bounds
        if bounds is not None:
            self._list_vertical_bounds = bounds
            # The root's 75%-of-Launch cap is stricter than the screen area.
            self._popup_height = min(self.root_menu._popup_height,
                                     max(1, bounds[1] - bounds[0]))
            self.setMaximumHeight(self._popup_height)

    def _virtual_leaf_item(self, node):
        """Temporary displayed leaf; never mutate the Files Exp model.

        Exp deliberately hides runnable JSON leaves (they belong to List).
        The / navigator must include them, otherwise ZIP and similar groups
        appear empty even when their registered commands are present.
        """
        row = node.get('row') or {}
        icon = self.launcher.row_icon(row)
        leaf = QStandardItem(icon, str(node.get('title') or ''))
        leaf.setEditable(False)
        leaf.setToolTip(str(row.get('description') or node.get('title') or ''))
        linked_path = None
        if node.get('kind') == 'linked_directory':
            raw = (node.get('row') or {}).get('launch_browse_target')
            if raw:
                linked_path = self.launcher.expander().expand(raw)
        leaf.setData({'virtual': node, 'pc': False, 'path': None,
                      'linked_path': linked_path}, _DATA_ROLE)
        leaf.setData(True, _LOADED_ROLE)
        return leaf

    def _transient_physical_folders(self, parent, path):
        """Read child folders without touching the Exp model or mount alias."""
        info = parent.data(_DATA_ROLE) or {}
        mount = info.get('slash_mount_origin')
        node = info.get('virtual')
        if (mount is None and isinstance(node, dict)
                and node.get('kind') == 'linked_directory'):
            mount = {'node': node, 'entry_path': str(path)}
        try:
            with os.scandir(path) as entries:
                children = sorted(((entry.name, entry.path) for entry in entries
                                   if entry.is_dir(follow_symlinks=False)),
                                  key=lambda pair: pair[0].casefold())
        except (OSError, ValueError):
            return
        for name, child_path in children:
            item = QStandardItem(self.launcher.row_icon({'icon_key': 'folder.yellow'}), name)
            item.setEditable(False)
            item.setToolTip(child_path)
            item.setData({'path': child_path, 'pc': False,
                          'slash_transient': True,
                          'slash_mount_origin': mount}, _DATA_ROLE)
            item.setData(True, _LOADED_ROLE)
            parent.appendRow(item)

    def _physical_file_item(self, path):
        """Read-only file entry from a physical directory's Files List."""
        row = {'item_kind': 'command', 'title': os.path.basename(path),
               'icon_key': 'file', '_browse_file': path}
        item = QStandardItem(self.launcher.row_icon(row), row['title'])
        item.setEditable(False)
        item.setToolTip(path)
        item.setData({'path': path, 'file': True, 'pc': False}, _DATA_ROLE)
        item.setData(True, _LOADED_ROLE)
        return item

    def _current_folder_item(self):
        """Context handle for THIS opened directory, never the Exp root.

        A root action would spuriously offer folder creation in Launch's
        top-level namespace. The source of a child column is the only safe
        authority; the unrelated currently highlighted List row is not.
        """
        if self.source_item is None or self._context_source is not None:
            return None  # No current directory on the unrooted Exp main list.
        # The FIRST / column is also an opened logical directory. Its source
        # comes from the breadcrumb (or its green-filled direct child), so it
        # must expose the same self-context row as deeper cascade columns.
        info = self.source_item.data(_DATA_ROLE) or {}
        node = info.get('virtual')
        if info.get('file') or info.get('pc'):
            return None
        path = info.get('linked_path') or info.get('path')
        if path and os.path.isdir(str(path)):
            context = {'current_folder': True, 'path': str(path), 'pc': False,
                       'studio_identity': info.get('studio_identity')}
            description = str(path)
        elif isinstance(node, dict) and node.get('kind') in ('page', 'folder', 'linked_directory'):
            # The selected JSON Page is also the current logical directory.
            # It has registration/edit actions just like an authored folder;
            # reuse the existing Studio context menu, never an OS folder menu.
            context = {'current_folder': True, 'virtual': node, 'pc': False}
            description = str(node.get('title') or '現在のフォルダー')
        else:
            return None
        item = QStandardItem(QIcon(), '（カレントフォルダー）')
        item.setEditable(False)
        item.setToolTip(description)
        item.setData(context, _DATA_ROLE)
        item.setData(True, _LOADED_ROLE)
        return item

    def _items(self):
        if self.source_item is None:
            parent = self.panel.model.invisibleRootItem()
        else:
            parent = self.source_item
            info = parent.data(_DATA_ROLE) or {}
            node = info.get('virtual')
            # Read actual Launch JSON children, INCLUDING runnable file leaves.
            # Do not resolve only virtual_exp_folders(), the Exp projection.
            if node is not None:
                if node.get('kind') == 'file':
                    return []
                if not parent.data(_LOADED_ROLE):
                    self.panel._expand_index(parent.index())
                existing = {}
                for n in range(parent.rowCount()):
                    child = parent.child(n)
                    child_info = child.data(_DATA_ROLE) if child is not None else None
                    child_node = (child_info or {}).get('virtual')
                    if child_node is not None:
                        existing[child_node.get('node_id')] = child
                children = node.get('children')
                if isinstance(children, (list, tuple)):
                    result = [existing.get(child.get('node_id')) or
                              self._virtual_leaf_item(child)
                              for child in children]
                else:
                    # Supports older virtual-tree projections containing only
                    # the Exp model's already-loaded direct children.
                    result = [parent.child(n) for n in range(parent.rowCount())
                              if isinstance((parent.child(n).data(_DATA_ROLE) or {}), dict)]
                # A linked directory can additionally expose physical files.
                if node.get('kind') == 'linked_directory':
                    path = info.get('linked_path')
                    if path and os.path.isdir(path):
                        physical = [parent.child(child) for child in range(parent.rowCount())
                                    if isinstance((parent.child(child).data(_DATA_ROLE) or {}), dict)
                                    and (parent.child(child).data(_DATA_ROLE) or {}).get('path')]
                        if physical:
                            result.extend(physical)
                        else:
                            # A detached JSON node has no loaded Exp children.
                            # Materialize only the ephemeral menu rows.
                            self._transient_physical_folders(parent, path)
                            result.extend(parent.child(i) for i in range(parent.rowCount())
                                          if (parent.child(i).data(_DATA_ROLE) or {}).get('slash_transient'))
                        result.extend(self._file_entries(path))
                rows = [item for item in result if item is not None and item.isEnabled()]
                current = self._current_folder_item()
                return ([current] if current is not None else []) + rows
            if info.get('file'):
                return []
            # Lazily project ONE level; the panel owns all registered folder
            # roots and PC drive resolution, not our menu.
            if not parent.data(_LOADED_ROLE):
                self.panel._expand_index(parent.index())
            if info.get('slash_transient') and not parent.rowCount():
                path = info.get('path')
                if path and os.path.isdir(path):
                    self._transient_physical_folders(parent, path)
        result = []
        for row in range(parent.rowCount()):
            item = parent.child(row)
            data = item.data(_DATA_ROLE) if item is not None else None
            if (not isinstance(data, dict) or data.get('separator_before_pc')
                    or not item.isEnabled()):
                continue
            result.append(item)
        # The current folder is a special *command target*, not an Exp child.
        # The root is strictly a list of Exp roots. Only a REAL opened folder
        # gains a self-context row; do not insert fake root-level operations.
        current = self._current_folder_item()
        if current is not None:
            result.insert(0, current)
        # Physical subdirectories are Exp children; Files List additionally
        # contains files. Both are navigable in this *independent* popup.
        if self.source_item is not None:
            info = self.source_item.data(_DATA_ROLE) or {}
            path = info.get('path')
            if path and os.path.isdir(path) and not info.get('file'):
                result.extend(self._file_entries(path))
                return self._sort_physical_items_for_list(result, path)
        return result

    def _sort_physical_items_for_list(self, items, folder):
        """Share physical Files List sort; preserve the current-folder command.

        Virtual Launch folders keep authored JSON ordering. A popup has no
        separate ordering preference: it reads the same folder ID key as List.
        """
        settings = getattr(self.launcher, 'settings', None)
        if settings is None:
            return items  # Headless older launchers and other callers.
        mode = load_directory_sort(settings, folder, SORT_LABELS)
        pinned, physical, remaining = [], [], []
        for item in items:
            info = item.data(_DATA_ROLE) or {}
            if info.get('current_folder'):
                pinned.append(item)
                continue
            path = info.get('path')
            if not path:
                remaining.append(item)
                continue
            physical.append((not bool(info.get('file')), path, item.text(), item))
        if not physical:
            return items
        return (pinned + remaining +
                sort_physical_popup_records(physical, mode))

    def _file_entries(self, folder):
        try:
            with os.scandir(folder) as entries:
                paths = sorted((entry.path for entry in entries
                                if entry.is_file(follow_symlinks=False)),
                               key=lambda name: os.path.basename(name).casefold())
        except (OSError, ValueError):
            return []
        # Include every file, even when the directory is much larger than the
        # on-screen viewport. Display height never limits filesystem results.
        return [self._physical_file_item(path) for path in paths]

    def _visible_rows(self):
        if self._scroll_tree is not None:
            # Detached actions are NOT a reliable visibility authority in Qt:
            # after removeAction(), only the real QTreeWidget rows determine
            # what is visible and selectable in a long folder column.
            return [action for action, row in self._scroll_items.items()
                    if not row.isHidden() and action.isEnabled()]
        return [a for a in self._action_items if a.isVisible() and a.isEnabled()]

    def _enable_fixed_scroll(self):
        """Use a real viewport for long columns, never QMenu's window-scroll.

        QMenu normally implements long lists by moving its whole popup when
        selecting an off-screen action. Pinning that window fights its native
        navigation (visible as flashing without actual row scrolling).
        QTreeWidget scrollToItem() moves *only the content*, with the frame,
        search field and popup position all stationary.
        """
        # Count search + frame/padding in the budget so a long list NEVER
        # forces native QMenu window-scroll below the Files List viewport.
        limit = max(1, (self._popup_height - 90) // self._item_height)
        # Short columns keep native QMenu QAction painting and keyboard
        # ownership; only tall columns need the scrolling QTreeWidget. Their
        # icon gutters are tuned to a shared inset without changing the
        # renderer itself (avoids the prior keyboard-cascade regression).
        if len(self._action_items) <= limit:
            return
        tree = QTreeWidget(self)
        tree.setObjectName('slashExpFixedScrollList')
        tree.setColumnCount(2)
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        tree.setIndentation(0)
        tree.setUniformRowHeights(True)
        tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setMouseTracking(True)
        tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Share the chosen column width with the scrolling viewport. A
        # hard-coded 233px tree used to squeeze long filenames to ~10 chars,
        # even when the enclosing QMenu had room to grow.
        tree.setFixedWidth(self.width() - 18)
        tree.setIconSize(QSize(18, 18))
        tree.header().setStretchLastSection(False)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        tree.setColumnWidth(1, 22)
        # The popup's scoped QSS owns List-matching row colors in both themes.
        # The scrolling viewport must not paint its own rectangular backing.
        tree.setAutoFillBackground(False)
        tree.viewport().setAutoFillBackground(False)
        # The action records remain available for filtering and dispatch, but
        # the native menu must not also render them beneath the scroll widget.
        for action in list(self._action_items):
            self.removeAction(action)
            title = self._display_text.get(action, action.text())
            row = QTreeWidgetItem([title, '›' if action in self._submenus or action in self._context_hint_actions else ''])
            row.setSizeHint(0, QSize(0, self._item_height))
            row.setTextAlignment(1, Qt.AlignmentFlag.AlignRight |
                                    Qt.AlignmentFlag.AlignVCenter)
            if (action.icon() is not None and
                    (not hasattr(action.icon(), 'isNull') or
                     not action.icon().isNull())):
                row.setIcon(0, action.icon())
            if action.toolTip():
                row.setToolTip(0, action.toolTip())
            info = self._action_items.get(action)
            details = info.data(_DATA_ROLE) if isinstance(info, QStandardItem) else {}
            if isinstance(details, dict) and details.get('current_folder'):
                # Same quiet shade as the short native-QMenu current row.
                # Test doubles may not expose Qt's QBrush or item background.
                if hasattr(row, 'setBackground'):
                    from PySide6.QtGui import QBrush
                    color = QBrush(QColor(self._current_folder_bg))
                    row.setBackground(0, color)
                    row.setBackground(1, color)
            row.setDisabled(not action.isEnabled())
            tree.addTopLevelItem(row)
            self._scroll_items[action] = row
            self._scroll_rows[row] = action
        # Leave headroom for the permanent search line, popup style padding,
        # and DPI rounding. Qt must never engage QMenu's *window* scroll arrows.
        tree.setFixedHeight(min(max(34, self._popup_height - 90),
                                len(self._action_items) * self._item_height + 4))
        holder = QWidgetAction(self)
        holder.setDefaultWidget(tree)
        self.addAction(holder)
        self._scroll_action = holder
        self._scroll_tree = tree
        tree.currentItemChanged.connect(self._on_scroll_current_changed)
        tree.itemClicked.connect(self._on_scroll_clicked)
        tree.installEventFilter(self)
        tree.viewport().installEventFilter(self)
        self._set_scroll_current_action(next(iter(self._action_items)))

    def _on_scroll_current_changed(self, row, _previous):
        action = self._scroll_rows.get(row)
        if action is not None:
            self._scroll_selected_action = action

    def _set_scroll_current_action(self, action):
        row = self._scroll_items.get(action)
        if row is None:
            return
        self._scroll_selected_action = action
        self._scroll_tree.setCurrentItem(row)
        # Qt's item viewport, not the popup, is the scrolling authority.
        self._scroll_tree.scrollToItem(
            row, QAbstractItemView.ScrollHint.EnsureVisible)
        # Re-activating QMenu's giant QWidgetAction for EVERY arrow key makes
        # QMenu try to scroll its whole window and visibly flicker on Windows.
        if self.activeAction() is not self._scroll_action:
            super().setActiveAction(self._scroll_action)

    def _on_scroll_clicked(self, row, _column):
        action = self._scroll_rows.get(row)
        if action is None:
            return
        self._set_scroll_current_action(action)
        if action in self._submenus:
            event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right,
                              Qt.KeyboardModifier.NoModifier)
            self._open_explicit_submenu(action, self._submenus[action], event)
        else:
            self.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return,
                                         Qt.KeyboardModifier.NoModifier))

    def _ensure_search(self):
        """Each column owns one permanent search bar; typing filters ONLY it."""
        if self._search_action is not None:
            return
        edit = SlashSearchEdit(self)
        edit.setObjectName('slashExpColumnSearch')
        edit.setPlaceholderText('この列を検索…')
        edit.setClearButtonEnabled(True)
        edit.setMinimumWidth(110)
        # Search styling is inherited from the Slash-only Files List palette.
        # A real layout, rather than CSS margins on QLineEdit, keeps BOTH
        # edges within the QMenu frame at Windows DPI / style scaling.
        holder = QWidget(self)
        holder.setObjectName('slashExpSearchHolder')
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(0)
        layout.addWidget(edit)
        edit.installEventFilter(self)
        # Opt-in trace only: compare this editor with working CascadeMenu.
        if os.environ.get("FRB_SLASH_IME_TRACE") == "1":
            from slash_ime_trace import watch_ime_menu
            watch_ime_menu(self, edit, "slash")
        action = QWidgetAction(self)
        action.setDefaultWidget(holder)
        self.addAction(action)
        self._search_action = action
        self._search_edit = edit
        edit.textChanged.connect(self._filter_rows)

    def _focus_search_for_ime(self):
        """Use the same IME ownership as the *working* CascadeMenu search.

        On Windows a native Qt.Popup can take focus back from the QWidgetAction
        QLineEdit immediately after popup().  CascadeMenu therefore focuses the
        menu itself, advertises ImEnabled and forwards real QInputMethodEvents
        to its embedded editor.  Synthetic QKeyEvents alone cannot start IME.
        Clicking the editor still allows native cursor/text editing.
        """
        if self._search_edit is not None and self.isVisible():
            if os.environ.get("FRB_SLASH_IME_TRACE") == "1":
                from slash_ime_trace import checkpoint_ime
                checkpoint_ime(self, "before_menu_focus_request")
            # Native activation is essential for Windows IME composition.
            # Don't substitute synthetic KeyEvents: they cannot start IME.
            self.activateWindow()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            if os.environ.get("FRB_SLASH_IME_TRACE") == "1":
                checkpoint_ime(self, "after_menu_focus_request")

    def _filter_rows(self, text):
        needle = str(text).strip().casefold()
        for action, item in self._action_items.items():
            visible = (not needle or needle in
                       self._full_text.get(action, item.text()).casefold())
            # The real item viewport, NOT a QAction detached from QMenu, owns
            # each row's visibility when a directory has many files.
            if self._scroll_tree is not None:
                self._scroll_items[action].setHidden(not visible)
            else:
                action.setVisible(visible)
            if action.menu() is not None:
                action.menu().hide()
                action.setMenu(None)
        # Calculate rows *after* changing their visibility: otherwise
        # clearing a search leaves the former hidden selection out-of-sync.
        rows = self._visible_rows()
        current = self._selected()[0]
        if self._scroll_tree is not None:
            if current not in rows:
                if rows:
                    self._set_scroll_current_action(rows[0])
                else:
                    self._scroll_selected_action = None
                    self._scroll_tree.clearSelection()
        elif current not in rows:
            self.setActiveAction(rows[0] if rows else None)

    def _may_have_children(self, item):
        info = item.data(_DATA_ROLE) or {}
        if info.get('current_folder'):
            return False  # Right = context commands, NEVER folder navigation.
        node = info.get('virtual')
        if node is not None:
            if node.get('kind') == 'file':
                return False
            children = node.get('children')
            if isinstance(children, (list, tuple)):
                if children:
                    return True
                # A linked directory is also a physical directory.
                if node.get('kind') != 'linked_directory':
                    return False
        if info.get('file'):
            return False
        if item.rowCount():
            return True
        path = info.get('linked_path') or info.get('path')
        if path and os.path.isdir(path):
            try:
                with os.scandir(path) as entries:
                    return any(entry.is_file(follow_symlinks=False)
                               or entry.is_dir(follow_symlinks=False) for entry in entries)
            except OSError:
                return False
        # PC / lazy virtual-tree roots are resolved by the existing Exp model.
        if info.get('pc') or node is not None:
            return bool(SlashExpMenu(self.launcher, self.panel,
                                    root=self.root_menu, source_item=item,
                                    parent=self)._items())
        return False

    def _pick_column_width(self, titles):
        """Determine the column's two-state width once from ORIGINAL names.

        Actual text measurement rather than row count/character count avoids
        switching widths for short Japanese labels or for a scrollbar alone.
        Search and tooltip retain their full, unchanged strings.
        """
        metrics = self.fontMetrics()
        width = max((metrics.horizontalAdvance(leading_page_emoji(name)[1])
                     for name in titles), default=0)
        desired = (SLASH_LONG_WIDTH if width > SLASH_LONG_TEXT_THRESHOLD
                   else SLASH_STANDARD_WIDTH)
        if self._context_source is not None:
            # Native Files operation menus use 218–225px, not the 300px
            # explorer column width. Elision preserves full action tooltip.
            desired = SLASH_OPERATION_WIDTH
        if self._exact_first_column_width is not None:
            desired = self._exact_first_column_width
        elif self._max_first_column_width is not None:
            desired = min(desired, self._max_first_column_width)
        self.setFixedWidth(desired)

    def _elided_caption(self, caption):
        # Reserve room for the icon, text gutters, a visible scrollbar and the
        # last 22px fixed-width chevron column. No second horizontal scrollbar.
        return self.fontMetrics().elidedText(
            caption, Qt.TextElideMode.ElideRight,
            max(90, self.width() - 92))

    def populate(self):
        if self._populated:
            return
        self._populated = True
        if self._context_source is not None:
            self._pick_column_width([action.text() for action in
                                     self._context_source.actions()
                                     if not action.isSeparator() and action.isVisible()
                                     and action.text().strip() != 'Filesリスト'])
            self._ensure_search()
            self._populate_context_actions()
            return
        if self._row_cache is None:
            self._row_cache = self._items()
        self._pick_column_width([item.text() for item in self._row_cache])
        self._ensure_search()
        for item in self._row_cache:
            # IMPORTANT: QMenu.addMenu(sub) makes Qt automatically open that
            # submenu merely by highlighting its row (hover or Up/Down).
            # A plain action has NO submenu until RIGHT is explicitly pressed.
            # The arrow glyph preserves the visual navigation hint.
            has_children = self._may_have_children(item)
            label = item.text()
            icon = item.icon()
            if icon is None or (hasattr(icon, 'isNull') and icon.isNull()):
                glyph, cleaned = leading_page_emoji(label)
                if glyph:
                    icon = page_emoji_icon(glyph)
                    label = cleaned
            # Elide before QMenu's native measurement: a long filename must
            # never stretch a popup off-screen or spill under another column.
            display_label = label  # scrolling tree may use all available pixels
            label = self._elided_caption(label)
            action = self.addAction(label)
            self._display_text[action] = display_label
            if icon is None or (hasattr(icon, 'isNull') and icon.isNull()):
                self._iconless_actions.add(action)
            else:
                action.setIcon(icon)
            action.setIconVisibleInMenu(True)
            action.setToolTip(item.toolTip())
            self._full_text[action] = item.text()
            self._action_items[action] = item
            if not has_children and not (item.data(_DATA_ROLE) or {}).get('current_folder'):
                # Mouse activation uses exactly the same terminal executor as
                # keyboard Enter. Branches still open their child on click.
                action.triggered.connect(
                    lambda checked=False, target=item:
                    self._close_then(lambda: self._commit_terminal(target)))
            if (item.data(_DATA_ROLE) or {}).get('current_folder'):
                self._context_hint_actions.add(action)
            if has_children:
                sub = SlashExpMenu(self.launcher, self.panel,
                                   root=self.root_menu, source_item=item, parent=self)
                sub._inherit_list_vertical_bounds()
                self._submenus[action] = sub
        if not self._action_items:
            empty = self.addAction('（項目なし）')
            empty.setEnabled(False)
        else:
            self._enable_fixed_scroll()

    def _populate_context_actions(self):
        """Project the *real* context QAction commands as a connected column.

        No fresh operation callbacks, no detached FRBContextMenu popup, and no
        shortcut competing with Files Exp/List.  New/Open-with submenus are
        projected recursively; Enter ultimately triggers their real QAction.
        """
        for command in self._context_source.actions():
            if not command.isSeparator() and command.text().strip() == 'Filesリスト':
                continue  # / Enter opens List directly; ordinary Exp menu unchanged.
            if command.isSeparator():
                # Slash-only Filesリスト filtering may leave a separator at
                # the top. Preserve the original source menu unchanged.
                if self._action_items:
                    self.addSeparator()
                continue
            if not command.isVisible():
                continue
            # A new QAction in this popup is only presentation. The original
            # QAction retains the already-wired filesystem/Studio callback.
            label = self._elided_caption(command.text())
            action = self.addAction(label)
            action.setIcon(command.icon())
            action.setIconVisibleInMenu(True)
            action.setEnabled(command.isEnabled())
            action.setToolTip(command.toolTip() or command.text())
            if command.icon().isNull():
                self._iconless_actions.add(action)
            self._action_items[action] = command
            self._full_text[action] = command.text()
            if command.menu() is not None:
                sub = SlashExpMenu(self.launcher, self.panel,
                                   root=self.root_menu, parent=self,
                                   context_source=command.menu())
                sub._inherit_list_vertical_bounds()
                self._submenus[action] = sub
            else:
                # A mouse click on the new column must still invoke the real
                # List/Exp QAction; presentation actions never duplicate code.
                action.triggered.connect(
                    lambda checked=False, target=command:
                    self._close_then(target.trigger))
        if not self._action_items:
            empty = self.addAction('（項目なし）')
            empty.setEnabled(False)
        else:
            self._enable_fixed_scroll()

    def paintEvent(self, event):
        super().paintEvent(event)
        # Paint a small native-looking triangle at the FAR RIGHT, only on
        # non-terminal rows. Qt paints the same lane when the submenu is
        # temporarily attached after an explicit Right key. No duplicates.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # QMenu reserves an icon gutter for ALL rows if any QAction has an
        # icon. Repaint only iconless rows with text aligned at the left edge;
        # otherwise authored Page emoji float in the middle of the gutter.
        if self._scroll_tree is not None:
            # QTreeWidget owns the item rows; the floating window still owns
            # its visible frame on ALL four sides.
            self._draw_floating_frame(painter)
            painter.end()
            return
        if hasattr(painter, 'drawText'):
            colors = self._slash_colors
            for action in self._iconless_actions:
                if not action.isVisible():
                    continue
                rect = self.actionGeometry(action)
                if not rect.isValid():
                    continue
                selected = action is self.activeAction()
                info = self._action_items.get(action)
                details = info.data(_DATA_ROLE) if isinstance(info, QStandardItem) else {}
                current_folder = isinstance(details, dict) and details.get('current_folder')
                background = (colors['selection'] if selected else
                              self._current_folder_bg if current_folder else
                              colors['panel'])
                painter.fillRect(rect.adjusted(2, 0, -7, 0), QColor(background))
                painter.setPen(QColor(colors['text']))
                caption = self.fontMetrics().elidedText(
                    self._full_text.get(action, action.text()),
                    Qt.TextElideMode.ElideRight, max(40, self.width() - 37))
                painter.drawText(rect.adjusted(8, 0, -17, 0),
                                 Qt.AlignmentFlag.AlignVCenter |
                                 Qt.AlignmentFlag.AlignLeft, caption)
        for action in (*self._submenus, *self._context_hint_actions):
            if not action.isVisible():
                continue
            # Native arrows on iconless rows are covered by the text-alignment
            # repaint above. Draw a single replacement in that case.
            if action.menu() is not None and action not in self._iconless_actions:
                continue
            rect = self.actionGeometry(action)
            if not rect.isValid():
                continue
            cx, cy = rect.right() - 13, rect.center().y()
            triangle = QPainterPath()
            triangle.moveTo(cx - 2, cy - 4)
            triangle.lineTo(cx + 2, cy)
            triangle.lineTo(cx - 2, cy + 4)
            triangle.closeSubpath()
            painter.fillPath(triangle, QColor(self._slash_colors['text']))
        # Must happen AFTER drawing captions/arrows; otherwise the selected
        # row may overpaint the border.  The former early paintEvent in this
        # class was shadowed by this method and never ran on Windows.
        self._draw_floating_frame(painter)
        painter.end()

    def eventFilter(self, obj, event):
        # Native Windows Menu key/keyboard ContextMenu is intentionally inert.
        # Pointer right-click is not affected.
        if (obj is self._search_edit or
                self._scroll_tree is not None and obj in
                (self._scroll_tree, self._scroll_tree.viewport())):
            if event.type() == getattr(QEvent.Type, 'ContextMenu', None):
                from PySide6.QtGui import QContextMenuEvent
                if event.reason() != QContextMenuEvent.Reason.Keyboard:
                    return super().eventFilter(obj, event)
                event.accept()
                return True
        if (self._scroll_tree is not None and
                obj in (self._scroll_tree, self._scroll_tree.viewport()) and
                event.type() == QEvent.Type.KeyPress):
            if event.key() == getattr(Qt.Key, 'Key_Menu', None):
                event.accept()
                return True
            # Leave all navigation under the same / menu key contract.
            self.keyPressEvent(event)
            return event.isAccepted()
        if (obj is self._search_edit and event.type() == QEvent.Type.KeyPress):
            # Japanese IME uses arrows to choose conversions and Enter to
            # finalize them. Do not turn those into folder navigation until
            # composition is committed/cancelled by the native editor.
            if event.key() == getattr(Qt.Key, 'Key_Menu', None):
                event.accept()
                return True
            if getattr(self._search_edit, 'ime_composing', False):
                return False
            # Slash is still the menu toggle outside IME composition.
            if is_slash_shortcut(event.key(), event.text(), event.modifiers()):
                self.root_menu.close()
                event.accept()
                return True
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down,
                               getattr(Qt.Key, 'Key_PageUp', None),
                               getattr(Qt.Key, 'Key_PageDown', None),
                               Qt.Key.Key_Right, Qt.Key.Key_Left,
                               getattr(Qt.Key, 'Key_Menu', None), Qt.Key.Key_Return, Qt.Key.Key_Enter,
                               Qt.Key.Key_Escape):
                self.keyPressEvent(event)
                return True
        return super().eventFilter(obj, event)

    def inputMethodEvent(self, event):
        # Exactly as in the existing Japanese-capable CascadeMenu: Qt sends
        # the OS-originated preedit/commit event to the focused menu window;
        # the *real* QLineEdit owns the composing text.  Never reconstruct a
        # Japanese string from QKeyEvent.text().
        if self._search_edit is None:
            self._ensure_search()
        if os.environ.get("FRB_SLASH_IME_TRACE") == "1":
            from slash_ime_trace import checkpoint_ime
            checkpoint_ime(self, "input_method_received",
                           preedit_len=len(event.preeditString()),
                           commit_len=len(event.commitString()))
        if self._search_edit is not None:
            QApplication.sendEvent(self._search_edit, event)
            event.accept()
            if os.environ.get("FRB_SLASH_IME_TRACE") == "1":
                checkpoint_ime(self, "input_method_forwarded")
            return
        super().inputMethodEvent(event)

    def inputMethodQuery(self, query):
        # The key missing contract compared with working CascadeMenu:
        # when the QMenu itself has focus, Windows asks the MENU (not its
        # unfocused child editor) whether IME is enabled.  Explicitly opt in.
        if query == Qt.InputMethodQuery.ImEnabled:
            return True
        if self._search_edit is not None:
            return self._search_edit.inputMethodQuery(query)
        return super().inputMethodQuery(query)

    def _selected(self):
        action = (self._scroll_selected_action if self._scroll_tree is not None
                  else self.activeAction())
        return action, self._action_items.get(action)

    def _selection_point(self, action):
        rect = self.actionGeometry(action)
        if rect.isValid():
            return self.mapToGlobal(QPoint(self.width() - 2, rect.center().y()))
        return self.mapToGlobal(QPoint(self.width(), 6))

    def _return_to_parent(self):
        parent = self.parentWidget()
        if not isinstance(parent, SlashExpMenu):
            self.root_menu.close()
            return
        selected = self.source_item if self._context_source is None else self._context_source
        self.hide()
        if parent._scroll_action is not None:
            parent._scroll_action.setMenu(None)
        for action, item in parent._action_items.items():
            if (item is selected or parent._submenus.get(action) is self
                    or parent._context_menus.get(action) is self):
                action.setMenu(None)  # Never reopen on hover / Up/Down.
                if parent._scroll_tree is not None:
                    parent._set_scroll_current_action(action)
                else:
                    parent.setActiveAction(action)
                break
        parent._focus_search_for_ime()

    def _close_then(self, callback, *, foreground_handoff=None, trace_enter=False):
        if trace_enter:
            _trace_current_folder_enter('before_root_close', self.launcher, self,
                                        ticket=foreground_handoff)
        self.root_menu.close()
        if trace_enter:
            _trace_current_folder_enter('after_root_close', self.launcher, self,
                                        ticket=foreground_handoff)
        if foreground_handoff is not None:
            # Try immediately, while the Enter keypress is still being
            # dispatched. Waiting for the next Qt tick may see the Enter KEYUP
            # as newer input and lose the guarded Windows handoff opportunity.
            restored = windows.finish_menu_enter_handoff(
                int(self.launcher.winId()), foreground_handoff)
            if trace_enter:
                _trace_current_folder_enter('immediate_restore', self.launcher,
                                            ticket=foreground_handoff, result=restored)
        # Navigate only after the Qt.Tool is hidden and its native grab freed.
        QTimer.singleShot(0, callback)

    def _build_existing_context(self, item):
        """Bind real List/Exp context actions as the NEXT menu column.

        Returning a QMenu rather than popping it at a global coordinate is
        essential: the prior implementation abandoned the whole / cascade.
        """
        info = item.data(_DATA_ROLE) or {}
        launcher = self.launcher
        node = info.get('virtual')
        if node is not None:
            identity = virtual_item_identity(node)
            menu = (launcher.show_virtual_launch_context(
                identity, None, return_menu=True) if identity else None)
            if menu is not None and info.get('current_folder'):
                # The self-context row is in Files List, even for a JSON
                # Page. Match its existing context menu (including the
                # Exp-column switch), not just the Studio edit commands.
                install_navigation = getattr(
                    launcher, '_install_files_column_navigation', None)
                if callable(install_navigation):
                    install_navigation(menu, 'list')
            return menu
        if info.get('pc'):
            menu = launcher._create_files_context_menu(launcher)
            menu.addAction('List列へ進む', lambda: launcher.navigate_files_exp_pc())
            return menu
        path = info.get('path')
        if info.get('file') and path and os.path.isfile(path):
            return launcher.show_slash_exp_file_context(path, None, return_menu=True)
        if path and os.path.isdir(path):
            return launcher.show_slash_exp_terminal_context(
                path, None, identity=info.get('studio_identity'), return_menu=True)
        return None

    def _attach_context(self, action, item):
        context = self._context_menus.get(action)
        if context is None:
            source = self._build_existing_context(item)
            if source is None:
                return None
            # The existing FRBContextMenu is a launcher-owned Qt.Tool and
            # cannot be a native Popup child: it loses arrow focus and jumps
            # toward (0,0) or a different monitor. Keep only its QAction data.
            context = SlashExpMenu(self.launcher, self.panel,
                                   root=self.root_menu, parent=self,
                                   context_source=source)
            context._inherit_list_vertical_bounds()
            context.populate()
            self._context_menus[action] = context
        return context

    def _pin_popup_position(self, position):
        """Fix a column origin for this entire popup session.

        QMenu's native scrolling can relocate an oversized popup when the
        active row moves off-screen. Keep the popup window stationary and let
        Qt scroll its *content* instead. Every newly opened column gets its
        own one-time origin; moving the highlight never recalculates it.
        """
        if self._fixed_popup_pos is None:
            self._fixed_popup_pos = QPoint(position.x(), position.y())
        if self.isVisible() and self.pos() != self._fixed_popup_pos:
            self.move(self._fixed_popup_pos)

    def _restore_popup_position(self):
        self._restore_position_queued = False
        if (self.isVisible() and self._fixed_popup_pos is not None
                and self.pos() != self._fixed_popup_pos):
            self.move(self._fixed_popup_pos)

    def moveEvent(self, event):
        super().moveEvent(event)
        if (self._fixed_popup_pos is not None and self.isVisible()
                and self.pos() != self._fixed_popup_pos
                and not self._restore_position_queued):
            self._restore_position_queued = True
            QTimer.singleShot(0, self._restore_popup_position)

    def _operation_popup_x(self, action):
        """Anchor a *command* column just beyond the visible row caption.

        Folder-browsing columns still cascade at the parent column edge.
        The width of the entire popup must never become a stand-in for the
        width of a selected filename.  Use the displayed (possibly elided)
        caption for BOTH regular QMenu rows and long fixed-scroll rows.
        """
        if self._scroll_tree is not None:
            item = self._scroll_items.get(action)
            if item is None:
                return None
            label = item.text(0) if hasattr(item, 'text') else getattr(item, 'caption', '')
            viewport = self._scroll_tree.viewport()
            start = viewport.mapToGlobal(QPoint(0, 0)).x() + 29
            measure = self._scroll_tree
        else:
            rect = self.actionGeometry(action)
            if not rect.isValid():
                return None
            label = action.text()
            start = self.mapToGlobal(QPoint(getattr(rect, 'left', lambda: 0)() + 35, 0)).x()
            measure = self
        # Keep the folder/file caption readable, with a comfortable gap.
        # If the text almost fills the column, fall back to its usual edge.
        caption_end = start + _approx_text_width(measure, label)
        right_edge = self.mapToGlobal(QPoint(self.width() - 1, 0)).x()
        return min(caption_end + 28, right_edge)

    def _align_open_submenu(self, action, submenu):
        """Place a new column once beside its row; never move it on scrolling."""
        if not submenu.isVisible():
            return
        if submenu._fixed_popup_pos is not None:
            submenu._restore_popup_position()
            return
        from PySide6.QtWidgets import QApplication
        if self._scroll_tree is not None:
            tree_row = self._scroll_items.get(action)
            if tree_row is None:
                return
            row = self._scroll_tree.visualItemRect(tree_row)
            # The scroll viewport is narrower than the menu frame. Position
            # the NEXT column beside the whole popup, not inside it.
            row_y = self._scroll_tree.viewport().mapToGlobal(QPoint(0, row.top())).y()
            point = QPoint(self.mapToGlobal(QPoint(self.width() - 1, 0)).x(), row_y)
        else:
            row = self.actionGeometry(action)
            if not row.isValid():
                return
            point = self.mapToGlobal(QPoint(self.width() - 1, row.top()))
        screen = QApplication.screenAt(point) or self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = submenu.width()
        height = submenu.height()
        x = point.x()
        # Operations (Copy/Paste/Rename/etc.) float next to the selected
        # caption, not at the far right of a wide exploration column.
        # Do not affect ordinary folder-to-folder cascading or operation
        # submenu placement within the blue command column.
        if self._context_source is None and submenu._context_source is not None:
            nearby = self._operation_popup_x(action)
            if nearby is not None:
                x = nearby
        # Prefer the right; fall back to immediately left of *this* column.
        if x + width > available.right() + 1:
            x = self.mapToGlobal(QPoint(0, 0)).x() - width + 1
        x = max(available.left(), min(x, available.right() - width + 1))
        # Cascades may open at a row near the bottom; slide the column UP
        # rather than letting it extend outside the Files List navigation area.
        top, bottom = (self.root_menu._list_vertical_bounds
                       or (available.top() + 10, available.bottom() - 9))
        top = max(top, available.top() + 10)
        bottom = min(bottom, available.bottom() - 9)
        y = min(max(point.y(), top), max(top, bottom - height))
        submenu._pin_popup_position(QPoint(x, y))

    def _open_explicit_submenu(self, action, submenu, event):
        """Open on Right only, never on Up/Down/hover."""
        submenu.populate()
        if self._scroll_tree is not None:
            # The single scroll-widget action is the submenu owner. Its
            # visible row is inside the QTreeWidget, so anchor below using
            # visualItemRect rather than a detached global popup coordinate.
            self._scroll_action.setMenu(submenu)
            self._set_scroll_current_action(action)
            # Qt's native QAction submenu lifetime keeps the parent open.
            super().keyPressEvent(event)
            if not submenu.isVisible():
                row = self._scroll_tree.visualItemRect(self._scroll_items[action])
                row_y = self._scroll_tree.viewport().mapToGlobal(QPoint(0, row.top())).y()
                point = QPoint(self.mapToGlobal(QPoint(self.width() - 1, 0)).x(), row_y)
                submenu.popup(point)
        else:
            action.setMenu(submenu)
            # Qt supplies the native cascade activation and popup lifetime.
            super().keyPressEvent(event)
        if submenu.isVisible():
            self._align_open_submenu(action, submenu)
        # Qt/Windows may reposition its native popup once more after this
        # event returns (especially with a tool-window parent). Correct again
        # after the Qt event loop has settled.
        QTimer.singleShot(0, lambda a=action, sub=submenu:
                          self._align_open_submenu(a, sub))
        rows = submenu._visible_rows()
        if rows and submenu._selected()[0] not in rows:
            if submenu._scroll_tree is not None:
                submenu._set_scroll_current_action(rows[0])
            else:
                submenu.setActiveAction(rows[0])
        submenu._focus_search_for_ime()

    def _commit_terminal(self, item, *, foreground_handoff=None):
        """Enter commits a folder to Files List; Right is navigation only."""
        info = item.data(_DATA_ROLE) or {}
        node = info.get('virtual')
        if info.get('current_folder'):
            path = info.get('linked_path') or info.get('path')
            if path and os.path.isdir(path):
                return self._commit_folder_and_focus(
                    self.launcher.navigate_files_exp_folder(
                        path, origin_panel=self.panel, origin_item=self.source_item),
                    foreground_handoff=foreground_handoff)
            if isinstance(node, dict):
                return self._commit_folder_and_focus(
                    self.launcher.navigate_virtual_launch_folder(node),
                    foreground_handoff=foreground_handoff)
            return False
        if node is not None:
            if node.get('kind') == 'file':
                # Files List's double-click URL route displays the embedded
                # third column. / navigation is a single-confirm gesture, so
                # reuse that same preview route before normal activation.
                # The preview function revalidates the current authored JSON
                # or bookmark URL and rejects other item types.
                view = getattr(self.launcher, 'expanded_view', None)
                preview = getattr(view, 'preview_bookmark_from_list', None)
                if callable(preview) and preview({'_launch_virtual_node': node}):
                    return True
                return self.launcher.activate_virtual_launch_item(node.get('row') or {})
            return self._commit_folder_and_focus(
                self.launcher.navigate_virtual_launch_folder(node))
        if info.get('pc'):
            return self._commit_folder_and_focus(
                self.launcher.navigate_files_exp_pc())
        path = info.get('linked_path') or info.get('path')
        if info.get('file') and path and os.path.isfile(path):
            # Exactly the same decision as Files List *double-click*: .md may
            # use Obsidian, Studio-managed JSON the embedded Studio host, and
            # other files their normal Windows file launcher. The decision is
            # made by the EXISTING eligibility/configuration logic, not a new
            # /-specific extension table.
            row = {'title': os.path.basename(path), '_browse_file': path,
                   'item_kind': 'command'}
            view = getattr(self.launcher, 'expanded_view', None)
            preview = getattr(view, 'preview_bookmark_from_list', None)
            if callable(preview) and preview(row):
                return True
            return self.launcher.run_file_path(row, path)
        if path and os.path.isdir(path):
            return self._commit_folder_and_focus(
                self.launcher.navigate_files_exp_folder(
                    path, origin_panel=self.panel, origin_item=item))
        return False

    def _commit_folder_and_focus(self, committed, *, foreground_handoff=None):
        """Folder Enter lands in Files List after the native menu closes.

        Only keyboard Enter on (カレントフォルダー) may recover Launch's native
        foreground; file execution and unrelated context actions never do.
        """
        _trace_current_folder_enter('folder_committed' if committed else 'folder_failed',
                                    self.launcher, ticket=foreground_handoff)
        if committed:
            QTimer.singleShot(0, lambda launcher=self.launcher, ticket=foreground_handoff:
                              focus_first_files_list_after_slash_enter(
                                  launcher, foreground_handoff=ticket))
        return committed

    def mouseReleaseEvent(self, event):
        # The native QMenu treats a plain QAction click as a completed command.
        # Intercept navigation branches: clicking them should expand, never
        # dismiss the complete / cascade with no action performed.
        if event.button() == Qt.MouseButton.LeftButton:
            action = self.actionAt(event.position().toPoint())
            submenu = self._submenus.get(action)
            if submenu is not None:
                self.setActiveAction(action)
                right = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right,
                                  Qt.KeyboardModifier.NoModifier)
                self._open_explicit_submenu(action, submenu, right)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def event(self, event):
        # Key_Menu may be delivered as a native keyboard ContextMenu event.
        # Consume it without changing selection, opening menus, or navigating.
        if event.type() == getattr(QEvent.Type, 'ContextMenu', None):
            from PySide6.QtGui import QContextMenuEvent
            if event.reason() != QContextMenuEvent.Reason.Keyboard:
                return super().event(event)
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == getattr(Qt.Key, 'Key_Menu', None):
            event.accept()
            return
        key = event.key()
        # If this QMenu (rather than the embedded editor) currently has OS
        # input focus, a Japanese preedit can still be active in that editor.
        # Navigation/escape/confirmation must not eat IME candidate keys.
        if (self._search_edit is not None
                and getattr(self._search_edit, 'ime_composing', False)
                and key in (Qt.Key.Key_Up, Qt.Key.Key_Down,
                            Qt.Key.Key_Left, Qt.Key.Key_Right,
                            getattr(Qt.Key, 'Key_PageUp', None),
                            getattr(Qt.Key, 'Key_PageDown', None),
                            getattr(Qt.Key, 'Key_Menu', None), Qt.Key.Key_Return, Qt.Key.Key_Enter,
                            Qt.Key.Key_Escape)):
            event.accept()
            return
        if is_slash_shortcut(key, event.text(), event.modifiers()):
            self.root_menu.close()
            event.accept()
            return
        if event.modifiers() not in (Qt.KeyboardModifier.NoModifier,
                                     Qt.KeyboardModifier.ShiftModifier):
            return super().keyPressEvent(event)
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            actions = self._visible_rows()
            if actions:
                current = self._selected()[0]
                pos = actions.index(current) if current in actions else (
                    0 if key == Qt.Key.Key_Up else -1)
                next_pos = (pos + (1 if key == Qt.Key.Key_Down else -1)) % len(actions)
                # Up/Down only changes the selection. No Qt-native delayed
                # submenu popup is permitted for any previously visited row.
                if self._scroll_tree is not None:
                    # DO NOT ask QMenu to scroll the popup window. The fixed
                    # list viewport scrolls its current row into view.
                    if self._scroll_action.menu() is not None:
                        self._scroll_action.setMenu(None)
                    self._set_scroll_current_action(actions[next_pos])
                else:
                    if current is not None and current.menu() is not None:
                        current.setMenu(None)
                    self.setActiveAction(actions[next_pos])
            event.accept()
            return
        if key in (getattr(Qt.Key, 'Key_PageUp', None),
                   getattr(Qt.Key, 'Key_PageDown', None)):
            # Always page the MENU's filtered list; never propagate a Page key
            # to the underlying Files List/Exp while the floating menu is open.
            actions = self._visible_rows()
            if actions:
                current = self._selected()[0]
                current_index = actions.index(current) if current in actions else -1
                viewport_height = (self._scroll_tree.viewport().height()
                                   if self._scroll_tree is not None
                                   else max(1, self.height() - 70))
                next_index = slash_menu_page_target(
                    current_index, len(actions), viewport_height,
                    self._item_height, -1 if key == getattr(Qt.Key, 'Key_PageUp', None) else 1)
                target = actions[next_index]
                if self._scroll_tree is not None:
                    if self._scroll_action.menu() is not None:
                        self._scroll_action.setMenu(None)
                    self._set_scroll_current_action(target)
                else:
                    if current is not None and current.menu() is not None:
                        current.setMenu(None)
                    self.setActiveAction(target)
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.root_menu.close()
            event.accept()
            return
        if key == Qt.Key.Key_Left:
            self._return_to_parent()
            event.accept()
            return
        if key not in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Ordinary text typed while an item is current filters the CURRENT
            # column, without sending the keystroke to Exp or Files List.
            text = event.text()
            if (text and text.isprintable() and not event.modifiers() &
                    (Qt.KeyboardModifier.ControlModifier |
                     Qt.KeyboardModifier.AltModifier)):
                QApplication.sendEvent(self._search_edit,
                    QKeyEvent(event.type(), key, event.modifiers(), text))
                event.accept()
                return
            if key == Qt.Key.Key_Backspace:
                self._search_edit.backspace()
                event.accept()
                return
            return super().keyPressEvent(event)
        action, item = self._selected()
        if item is None:
            event.accept()
            return
        if (self._context_source is None and
                (item.data(_DATA_ROLE) or {}).get('current_folder')):
            if key == Qt.Key.Key_Right:
                submenu = self._attach_context(action, item)
                if submenu is not None:
                    self._open_explicit_submenu(action, submenu, event)
            else:
                # Enter on (カレントフォルダー) closes an activated Qt.Tool.
                # On Windows the OS may reactivate Chrome behind Launch.
                # Capture the foreground/last-input guard *before* closing.
                _trace_current_folder_enter('enter_before_capture', self.launcher, self)
                handoff = windows.capture_menu_enter_handoff(
                    int(self.winId()), int(self.launcher.winId())) if windows.IS_WINDOWS else None
                _trace_current_folder_enter('enter_after_capture', self.launcher, self,
                                            ticket=handoff)
                self._close_then(lambda target=item, ticket=handoff:
                    self._commit_terminal(target, foreground_handoff=ticket),
                    foreground_handoff=handoff, trace_enter=True)
            event.accept()
            return
        # Determine the terminal boundary ONLY when this row is activated.
        submenu = self._submenus.get(action)
        if submenu is not None:
            if key == Qt.Key.Key_Right:
                self._open_explicit_submenu(action, submenu, event)
            elif self._context_source is None:
                # Folder Enter opens it in Files List; Right explores children.
                # Context submenus still require a final command: a QAction is
                # not an Exp model item and must never be committed as one.
                self._close_then(lambda target=item: self._commit_terminal(target))
            event.accept()
            return
        if self._context_source is not None:
            # Final context command: execute the ORIGINAL QAction, not the
            # presentation action, to keep all List/Exp action semantics.
            if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                self._close_then(lambda command=item: command.trigger())
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            submenu = self._attach_context(action, item)
            if submenu is not None:
                self._open_explicit_submenu(action, submenu, event)
        else:
            self._close_then(lambda target=item: self._commit_terminal(target))
        event.accept()


def _restore_launch_after_current_folder_enter(launcher, handoff):
    """One guarded Win32 recovery; a later user input cancels the ticket."""
    view = getattr(launcher, 'expanded_view', None)
    if (handoff is None or view is None or not view.isVisible()
            or getattr(view, '_workspace_mode', None) != 'files'):
        return False
    restored = windows.finish_menu_enter_handoff(int(launcher.winId()), handoff)
    _trace_current_folder_enter('deferred_restore', launcher,
                                ticket=handoff, result=restored)
    if restored:
        launcher.activateWindow()
    return restored


def focus_first_files_list_after_slash_enter(launcher, *, foreground_handoff=None):
    """Return List to its first row, optionally recovering Qt.Tool foreground.

    The native recovery is restricted to (カレントフォルダー) keyboard Enter.
    The delayed retry covers Windows' native activation after Tool hides; it
    cannot steal focus if another physical input has happened since Enter.
    """
    view = getattr(launcher, 'expanded_view', None)
    if (view is None or not view.isVisible()
            or getattr(view, '_workspace_mode', None) != 'files'):
        return False
    pane = getattr(view, 'middle', None)
    tree = getattr(pane, 'tree', None)
    if tree is None:
        return False
    if foreground_handoff is not None:
        _restore_launch_after_current_folder_enter(launcher, foreground_handoff)
        # Native Tool deactivation may settle *after* the next event-loop tick.
        # A short guarded retry is safe only if no newer user input occurred.
        QTimer.singleShot(90, lambda app=launcher, ticket=foreground_handoff:
                          _restore_launch_after_current_folder_enter(app, ticket))
    view._focus_files_keyboard_area('list')
    first = next((row for idx in range(tree.topLevelItemCount())
                  if (row := tree.topLevelItem(idx)) is not None
                  and view.row_data(row) is not None), None)
    if first is not None:
        tree.setCurrentItem(first)
        tree.scrollToItem(first)
    # Explicit focus again AFTER current-row selection, not on Exp or search.
    tree.setFocus(Qt.FocusReason.OtherFocusReason)
    _trace_current_folder_enter('list_focus_requested', launcher,
                                ticket=foreground_handoff,
                                result=bool(tree.hasFocus()) if hasattr(tree, 'hasFocus') else None)
    return True


class _SlashToolDismissGuard(QObject):
    """Restore click-away dismissal when Qt.Tool replaces Qt.Popup.

    This filter observes only mouse *presses*. Keyboard and IME events are
    never intercepted, so all existing Search/Right/Left/Enter behavior stays
    with the menu. Clicking inside any column (including a child editor) is
    not a dismissal. Clicking elsewhere in Launch closes the complete chain.
    """

    def __init__(self, root):
        super().__init__(root)
        self.root = root

    def eventFilter(self, obj, event):
        if (event.type() != QEvent.Type.MouseButtonPress
                or not self.root.isVisible() or not isinstance(obj, QWidget)):
            return False
        widget = obj
        while widget is not None:
            if (isinstance(widget, SlashExpMenu)
                    and widget.root_menu is self.root):
                return False
            widget = widget.parentWidget()
        self.root.close()
        return False  # The click must still reach its intended target.


def _slash_tool_chain_has_composition(menu):
    """Do not close while native IME is selecting conversion candidates."""
    editor = getattr(menu, '_search_edit', None)
    if editor is not None and getattr(editor, 'ime_composing', False):
        return True
    for child in (*menu._submenus.values(), *menu._context_menus.values()):
        if child.isVisible() and _slash_tool_chain_has_composition(child):
            return True
    return False


def _close_visible_slash_children(menu):
    """Tool submenu windows must never outlive their closed root."""
    for child in (*menu._submenus.values(), *menu._context_menus.values()):
        if child.isVisible():
            _close_visible_slash_children(child)
            child.close()


def popup_exp_navigator(launcher, panel, anchor, *, first_column_width=None,
                        extra_name_gutter=0,
                        list_bottom_y=None, source_item=None, list_height=None,
                        parent_left=None):
    """Create one breadcrumb-rooted session; never register a new Exp root."""
    previous = getattr(launcher, '_slash_exp_navigation_menu', None)
    if previous is not None:
        try:
            previous.close()
        except RuntimeError:
            pass
    # Parent to Launch's topmost window. Qt.Tool becomes an active native
    # window for Japanese IME and our guard provides outside-click closing.
    menu = SlashExpMenu(launcher, panel, source_item=source_item, parent=launcher)
    if list_height is not None:
        # New floating mode: Launch window may be shorter than this popup.
        # Files List *height* is the hard cap; the monitor's work area keeps
        # the popup off the taskbar (with 10px of breathing room).
        screen = (QApplication.screenAt(anchor) or
                  getattr(launcher, 'screen', lambda: None)() or
                  QApplication.primaryScreen())
        if screen is not None:
            work = screen.availableGeometry()
            safe_top = work.top() + 10
            safe_bottom = work.bottom() - 9
            menu._list_vertical_bounds = (safe_top, safe_bottom)
            menu._popup_height = slash_popup_height_budget(
                list_height, launcher.height(), safe_bottom-safe_top)
        else:
            menu._popup_height = slash_popup_height_budget(
                list_height, launcher.height(), int(list_height))
        menu.setMaximumHeight(menu._popup_height)
    elif list_bottom_y is not None:
        # Legacy tests/callers retain the old viewport-bounded contract.
        bottom = int(list_bottom_y)
        top = int(anchor.y())
        if bottom > top:
            menu._list_vertical_bounds = (top, bottom)
            menu._popup_height = bottom - top
            menu.setMaximumHeight(menu._popup_height)
    if first_column_width is not None:
        # Mirror the Name header's ACTUAL width, even for unusually long
        # filenames or a user-resized narrow column. Set before populate()
        # so both native rows and the long-list scrolling viewport agree.
        menu._exact_first_column_width = (int(first_column_width)
                                          + max(0, int(extra_name_gutter)))
    menu.populate()
    if not menu._action_items:
        menu.deleteLater()
        return False
    launcher._slash_exp_navigation_menu = menu
    application = QApplication.instance()
    click_guard = _SlashToolDismissGuard(menu) if application is not None else None
    if click_guard is not None:
        application.installEventFilter(click_guard)

    def on_app_state_changed(state):
        # An external application can receive a click without Qt delivering
        # a MouseButtonPress to us.  Close on app deactivation, but leave IME
        # candidate selection alone while its preedit is active.
        if (state == Qt.ApplicationState.ApplicationInactive and menu.isVisible()
                and not _slash_tool_chain_has_composition(menu)):
            QTimer.singleShot(50, lambda: menu.close()
                              if (menu.isVisible() and
                                  application.applicationState() ==
                                      Qt.ApplicationState.ApplicationInactive and
                                  not _slash_tool_chain_has_composition(menu))
                              else None)

    if application is not None:
        application.applicationStateChanged.connect(on_app_state_changed)

    def on_hidden():
        if getattr(launcher, '_slash_exp_navigation_menu', None) is menu:
            launcher._slash_exp_navigation_menu = None
        _close_visible_slash_children(menu)
        if application is not None:
            if click_guard is not None:
                application.removeEventFilter(click_guard)
            try:
                application.applicationStateChanged.disconnect(on_app_state_changed)
            except (TypeError, RuntimeError):
                pass
        # Context actions are scheduled on the next tick, never delete them
        # before the menu's focus restoration has completed.
        QTimer.singleShot(250, menu.deleteLater)

    menu.aboutToHide.connect(on_hidden)
    # The caller anchors only the FIRST column at Files List's Name header.
    # Do not shift it to reserve hypothetical columns: each actual child
    # column is independently placed beside the current selection.
    screen = (QApplication.screenAt(anchor) or
              getattr(launcher, 'screen', lambda: None)() or
              QApplication.primaryScreen())
    if screen is not None:
        bounds = screen.availableGeometry()
        max_left = max(bounds.left(), bounds.right() + 1 - menu.width())
        anchor = QPoint(max(bounds.left(), min(anchor.x(), max_left)), anchor.y())
    menu.popup(anchor)
    if list_height is not None and screen is not None:
        # QMenu acquires its true width/height only after popup().  Slide up
        # when the parent row is near the taskbar; never grow beyond List.
        # Keep this position fixed during Up/Down internal scrolling.
        work = screen.availableGeometry()
        x, y = popup_xy(anchor.x(), anchor.y(), menu.width(), menu.height(),
            work_left=work.left(), work_top=work.top(),
            work_right=work.right()+1, work_bottom=work.bottom()+1,
            parent_left=parent_left)
        menu.move(QPoint(x, y))
        menu._pin_popup_position(QPoint(x, y))
    if menu._scroll_tree is not None:
        menu._set_scroll_current_action(next(iter(menu._action_items)))
    else:
        menu.setActiveAction(next(iter(menu._action_items)))
    # Lock only AFTER QMenu has made its initial screen-edge adjustment.
    # Subsequent Up/Down scrolling must never relocate the popup window.
    QTimer.singleShot(0, lambda m=menu: m._pin_popup_position(m.pos())
                      if m.isVisible() else None)
    menu._focus_search_for_ime()
    # Native activation may reassign focus once the first show event settles; restore
    # the actual input widget after that, never through a synthetic key event.
    QTimer.singleShot(0, lambda m=menu: m._focus_search_for_ime())
    return True
