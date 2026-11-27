"""One owner of transient processing feedback, independent of command origin.

The operation chooses a display mode; the owner implements its presentation.
Persistent index state and external/Commander windows are not managed here.
"""
from contextlib import contextmanager

CURSOR = 'CURSOR'
MESSAGE = 'MESSAGE'
PROGRESS = 'PROGRESS'


class ProcessingDisplay:
    def __init__(self, application, wait_cursor, exclude_input, dialog_factory=None):
        self.application = application
        self.wait_cursor = wait_cursor
        self.exclude_input = exclude_input
        self.dialog_factory = dialog_factory
        self.depth = 0
        self.paused = 0
        self.owns_cursor = False

    def _sync_cursor(self):
        desired = self.depth > 0 and self.paused == 0
        if desired and not self.owns_cursor:
            self.application.setOverrideCursor(self.wait_cursor)
            self.owns_cursor = True
        elif not desired and self.owns_cursor:
            self.application.restoreOverrideCursor()
            self.owns_cursor = False

    @contextmanager
    def waiting_for_user(self):
        """Human confirmation/input is not processing time."""
        self.paused += 1
        self._sync_cursor()
        try:
            yield
        finally:
            self.paused -= 1
            self._sync_cursor()

    @contextmanager
    def display(self, mode=CURSOR, *, verb='', total=1, parent=None):
        if mode not in (CURSOR, MESSAGE, PROGRESS):
            raise ValueError('Unsupported processing display mode: ' + str(mode))
        self.depth += 1
        dialog = None
        try:
            self._sync_cursor()
            if mode != CURSOR:
                if self.dialog_factory is None:
                    raise RuntimeError('Processing display dialog is not configured')
                dialog = self.dialog_factory(parent, verb, total, mode=mode)
                dialog.show()
                if mode == PROGRESS:
                    dialog.advance(0, total)
            # Paint the closed menu/cursor/dialog before entering synchronous
            # work. Never accept a second user command in this paint pass.
            if dialog is not None:
                self.application.processEvents(self.exclude_input)
            yield dialog.advance if mode == PROGRESS else (lambda *args: None)
        finally:
            try:
                if dialog is not None:
                    try:
                        dialog.close()
                    finally:
                        dialog.deleteLater()
            finally:
                self.depth -= 1
                self._sync_cursor()

    def run(self, callback, mode=CURSOR, **kwargs):
        with self.display(mode, **kwargs):
            return callback()


_shared = None


def processing_display(dialog_factory=None):
    """All Qt callers share the same cursor ownership, including nested work."""
    global _shared
    if _shared is None:
        from PySide6.QtCore import Qt, QEventLoop
        from PySide6.QtWidgets import QApplication
        _shared = ProcessingDisplay(QApplication, Qt.CursorShape.WaitCursor,
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
    if dialog_factory is not None:
        _shared.dialog_factory = dialog_factory
    return _shared
