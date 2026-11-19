"""Move frameless windows by dragging existing, noninteractive header surfaces.

Install only on decorative widgets or a header background. QLineEdit,
QPushButton, and other active controls deliberately receive no filter, so
selection, editing, and clicks retain their existing behavior.
"""

from PySide6.QtCore import QObject, QEvent, Qt


class PassiveHeaderDrag(QObject):
    """Move by a passive header; toggle maximize on workspace blank-band double-click."""

    _WORKSPACE_DRAG_HANDLE = 'expandedWorkspaceDragHandle'
    _DRAG_THRESHOLD = 5

    def __init__(self, window, on_header_press=None):
        super().__init__(window)
        self.window = window
        self._on_header_press = on_header_press
        self._origin_pointer = None
        self._origin_window = None
        self._active = False
        self._pending_workspace_drag = False

    def _reset_drag(self):
        self._active = False
        self._pending_workspace_drag = False
        self._origin_pointer = None
        self._origin_window = None

    def eventFilter(self, widget, event):
        kind = event.type()
        is_workspace_blank = (getattr(widget, 'objectName', lambda: '')()
                              == self._WORKSPACE_DRAG_HANDLE)
        property_getter = getattr(widget, 'property', None)
        header_mode = (property_getter('frbHeaderDoubleClick')
                       if callable(property_getter) else None)
        # Only explicitly registered, passive title/header areas are draggable.
        # Children such as the breadcrumb, input boxes, close/maximize buttons
        # and the Files List column headers remain native Qt controls.
        allow_double_click = (is_workspace_blank or
                              header_mode in ('window', 'third'))
        if (allow_double_click
                and kind == getattr(QEvent.Type, 'MouseButtonDblClick', None)
                and event.button() == Qt.MouseButton.LeftButton):
            self._reset_drag()
            if header_mode == 'third':
                self.window.maximize_launch_then_third()
            else:
                self.window.toggle_maximize_restore()
            event.accept()
            return True

        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self._on_header_press is not None:
                self._on_header_press()
            self._reset_drag()
            self._origin_pointer = event.globalPosition().toPoint()
            self._origin_window = self.window.pos()
            if allow_double_click:
                # A native startSystemMove on mouse DOWN consumes Windows'
                # second click. Wait for real movement before starting it;
                # a stationary double click can therefore maximize reliably.
                self._pending_workspace_drag = True
            else:
                handle = self.window.windowHandle()
                if handle and handle.startSystemMove():
                    self._origin_pointer = None
                    self._origin_window = None
                else:
                    self._active = True
            event.accept()
            return True

        if self._pending_workspace_drag and kind == QEvent.Type.MouseMove:
            if not event.buttons() & Qt.MouseButton.LeftButton:
                self._reset_drag()
                return False
            point = event.globalPosition().toPoint()
            delta = point - self._origin_pointer
            if abs(delta.x()) + abs(delta.y()) < self._DRAG_THRESHOLD:
                event.accept()
                return True
            self._pending_workspace_drag = False
            handle = self.window.windowHandle()
            if handle and handle.startSystemMove():
                self._origin_pointer = None
                self._origin_window = None
            else:
                self._active = True
                self.window.move(self._origin_window + delta)
            event.accept()
            return True

        if self._active and kind == QEvent.Type.MouseMove:
            if self._origin_pointer is not None and event.buttons() & Qt.MouseButton.LeftButton:
                self.window.move(self._origin_window + event.globalPosition().toPoint() - self._origin_pointer)
            event.accept()
            return True

        if (self._active or self._pending_workspace_drag) and kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            self._reset_drag()
            event.accept()
            return True

        return False
