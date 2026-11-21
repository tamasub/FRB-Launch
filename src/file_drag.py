"""Outbound file-copy drag for launcher tree rows and cascade actions.

Files List defaults to native Windows Shell; other callers retain Qt URLs.
No file bytes are loaded, no copy/move/delete is performed by FRB Launch.
"""
from PySide6.QtCore import Qt, QMimeData, QUrl
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget
from file_drag_paths import file_paths_for_drag


def begin_file_copy_drag(widget, row, *, native_shell_mode=False):
    """Start a copy-only OS drag with one or several selected physical files.

    For popup/menu callers ``row`` is a single dictionary.  Expanded Files
    passes selected dictionaries in visible order.  Windows drag receivers
    therefore get every file URL in the same operation, not just currentItem.
    """
    rows = [row] if isinstance(row, dict) else list(row or ())
    paths = file_paths_for_drag(rows)
    if not paths:
        return False
    # The Files List owner selects the native Shell mode from state.ini.
    # Other callers and the ini rollback keep their original Qt URL path.
    if native_shell_mode:
        try:
            from native_shell_drag import begin_native_shell_file_drag
            if begin_native_shell_file_drag(widget, paths):
                return True
        except (OSError, RuntimeError, AttributeError, ValueError):
            # Native initialization failed BEFORE a drag could start: retain
            # the trusted original Qt file drag rather than lose the gesture.
            pass
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(path) for path in paths])
    # Clipboard/OLE Windows consumers should see COPY, never MOVE.
    mime.setData('application/x-qt-windows-mime;value="Preferred DropEffect"',
                 (1).to_bytes(4, 'little'))
    drag = QDrag(widget)
    drag.setMimeData(mime)
    drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
    return True


class ExternalFileDragTree(QTreeWidget):
    """Drag selected physical file outside; keep click and keyboard handling."""

    def __init__(self, parent=None, row_resolver=None):
        super().__init__(parent)
        self._file_drag_row_resolver = row_resolver
        # Other consumers of this tree stay on Qt; Files List overrides it.
        self.native_shell_drag_mode = False
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(False)

    def startDrag(self, supported_actions):
        current = self.currentItem()
        if current is None:
            return
        # Only the expanded middle column uses ExtendedSelection.  A drag
        # started on an already selected file should carry the whole selection
        # (Ctrl/Shift), not just its currentItem.  On an unselected row, never
        # silently drag a different set of files from elsewhere in the view.
        if (self.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
                and current.isSelected()):
            items = sorted(self.selectedItems(),
                           key=self.indexOfTopLevelItem)
        else:
            items = [current]
        rows = [(self._file_drag_row_resolver(item) if self._file_drag_row_resolver
                 else item.data(0, Qt.ItemDataRole.UserRole)) for item in items]
        begin_file_copy_drag(self, rows, native_shell_mode=getattr(self, 'native_shell_drag_mode', False))
