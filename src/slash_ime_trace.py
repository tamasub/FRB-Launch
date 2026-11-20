"""Opt-in, text-redacted Qt/Windows IME event trace for Launch menu search.

Enable with FRB_SLASH_IME_TRACE=1 before starting the *source* application.
The trace records focus/IME/key event metadata for both the existing working
CascadeMenu editor and the SlashExpMenu editor. It NEVER records typed text,
preedit/commit strings, paths, document names, or clipboard contents.
"""

import datetime
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import QApplication

_TRACE_ENABLED = os.environ.get('FRB_SLASH_IME_TRACE', '').strip().lower() in (
    '1', 'true', 'on', 'yes')
_TRACE_SINGLETON = None


class _ImeTrace(QObject):
    _EVENTS = {
        QEvent.Type.FocusIn,
        QEvent.Type.FocusOut,
        QEvent.Type.InputMethod,
        QEvent.Type.InputMethodQuery,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
        QEvent.Type.WindowActivate,
        QEvent.Type.WindowDeactivate,
        QEvent.Type.Show,
        QEvent.Type.Hide,
    }

    def __init__(self, app):
        super().__init__(app)
        path = os.environ.get('FRB_SLASH_IME_LOG', '').strip()
        self.path = Path(path) if path else (Path(tempfile.gettempdir()) / 'FRBLaunch'
                                            / 'exp_keyboard_ime_trace.log')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open('a', encoding='utf-8', buffering=1)
        self._watched = {}
        self._serial = 0
        app.installEventFilter(self)
        app.focusChanged.connect(self._focus_changed)
        self.emit('session_started', 'system', 'diagnostic_only=1 text_redacted=1')

    def emit(self, event, role, detail=''):
        self._serial += 1
        now = datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')
        self._file.write(f'{now} [{self._serial:05d}] {role} {event} {detail}\n')

    @staticmethod
    def _describe(obj):
        if obj is None:
            return 'none'
        try:
            # Qt object names and classes only; NEVER widget text or window title.
            name = obj.objectName() if hasattr(obj, 'objectName') else ''
            cls = type(obj).__name__
            return f'{cls}#{name}' if name else cls
        except RuntimeError:
            return 'deleted'

    @staticmethod
    def _safe(obj, name):
        if obj is None:
            return -1
        fn = getattr(obj, name, None)
        if not callable(fn):
            return -1
        try:
            return int(bool(fn()))
        except (RuntimeError, TypeError):
            return -1

    def _focus_snapshot(self, menu=None, editor=None):
        app = QApplication.instance()
        focus = app.focusWidget() if app else None
        active = app.activeWindow() if app else None
        popup = app.activePopupWidget() if app else None
        try:
            im = app.inputMethod() if app else None
            locale = im.locale().name() if im else 'none'
            im_visible = self._safe(im, 'isVisible')
            im_anim = self._safe(im, 'isAnimating')
        except (AttributeError, RuntimeError):
            locale, im_visible, im_anim = 'error', -1, -1
        return (
            f'focus={self._describe(focus)} active={self._describe(active)} '
            f'popup={self._describe(popup)} menu_visible={self._safe(menu, "isVisible")} '
            f'menu_focus={self._safe(menu, "hasFocus")} '
            f'edit_focus={self._safe(editor, "hasFocus")} '
            f'edit_visible={self._safe(editor, "isVisible")} '
            f'ime_locale={locale} ime_visible={im_visible} ime_animating={im_anim}'
        )

    def watch(self, menu, editor, category):
        for obj, role in ((menu, f'{category}.menu'), (editor, f'{category}.edit')):
            if obj is None:
                continue
            key = id(obj)
            self._watched[key] = (role, menu, editor)
            # Use an immutable id to unregister an invalidated C++ wrapper.
            try:
                obj.destroyed.connect(lambda _=None, k=key: self._watched.pop(k, None))
            except (RuntimeError, AttributeError):
                pass
        self.emit('watch', category, self._focus_snapshot(menu, editor))

    def checkpoint(self, menu, label, **facts):
        record = self._watched.get(id(menu))
        if record is None:
            return
        role, _menu, editor = record
        allowed = ' '.join(f'{name}={value}' for name, value in facts.items())
        self.emit(label, role, f'{allowed} {self._focus_snapshot(menu, editor)}')

    def _focus_changed(self, old, new):
        # Even if another widget steals focus, record only widget type / object name.
        if not self._watched:
            return
        self.emit('focusChanged', 'application',
                  f'from={self._describe(old)} to={self._describe(new)}')

    def eventFilter(self, obj, event):
        record = self._watched.get(id(obj))
        if record is None or event.type() not in self._EVENTS:
            return False
        role, menu, editor = record
        typ = event.type()
        detail = ''
        if typ in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            # Key identities and length, not QKeyEvent.text() (privacy).
            detail = (f'key={int(event.key())} mods={int(event.modifiers().value)} '
                      f'text_len={len(event.text())} accepted={int(event.isAccepted())}')
        elif typ == QEvent.Type.InputMethod:
            detail = (f'preedit_len={len(event.preeditString())} '
                      f'commit_len={len(event.commitString())} '
                      f'accepted={int(event.isAccepted())}')
        elif typ == QEvent.Type.InputMethodQuery:
            # Queries can be issued many times; filter spam and preserve signal.
            try:
                detail = f'queries={int(event.queries().value)}'
            except (AttributeError, TypeError):
                detail = 'queries=unknown'
        detail = f'{detail} {self._focus_snapshot(menu, editor)}'
        self.emit(typ.name, role, detail)
        return False  # Diagnostic NEVER interferes with keyboard/IME handling.


def _instance():
    global _TRACE_SINGLETON
    if not _TRACE_ENABLED:
        return None
    if _TRACE_SINGLETON is None:
        app = QApplication.instance()
        if app is None:
            return None
        _TRACE_SINGLETON = _ImeTrace(app)
    return _TRACE_SINGLETON


def watch_ime_menu(menu, editor, category):
    tracer = _instance()
    if tracer is not None:
        tracer.watch(menu, editor, category)


def checkpoint_ime(menu, label, **safe_facts):
    tracer = _instance()
    if tracer is not None:
        tracer.checkpoint(menu, label, **safe_facts)
