"""Shared background display: actual Qt rendering and worker completion.

Run with PySide6 installed; offscreen does not establish Windows compositor behavior.
"""
import ast
import os
from pathlib import Path
import threading

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtCore import Qt, QTimer, QEventLoop, QObject, QEvent
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLabel,
                               QSizePolicy, QProgressBar, QWidget)
from PySide6.QtTest import QTest
from launch_appearance import theme_palette
from processing_display import ProcessingDisplay, MESSAGE, PROGRESS


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def display(app):
    # Actual production dialog without importing Windows-only Launcher.
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'src/app.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'FilesOperationProgress')
    scope = dict(globals())
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 '<FilesOperationProgress>', 'exec'), scope)
    dialogs = []
    def factory(*args, **kwargs):
        dialog = scope['FilesOperationProgress'](*args, **kwargs)
        dialogs.append(dialog)
        return dialog
    owner = QWidget()
    manager = ProcessingDisplay(app, Qt.CursorShape.WaitCursor,
                                QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, factory)
    yield manager, dialogs, owner
    owner.deleteLater()
    app.processEvents()


@pytest.mark.parametrize('mode', [MESSAGE, PROGRESS])
def test_heading_paints_and_animates_during_background_operation(app, display, mode):
    manager, dialogs, owner = display
    main_id = threading.get_ident()
    entered = threading.Event()
    release = threading.Event()
    observed = []
    painted = []

    class PaintObserver(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Paint and entered.is_set():
                painted.append(True)
            return False
    observer = PaintObserver()
    def work():
        assert threading.get_ident() != main_id
        entered.set()
        assert release.wait(4), 'GUI event loop did not continue during processing'
        return 'completed'
    def inspect():
        if not entered.is_set():
            return
        dialog = dialogs[0]
        if not observed:
            dialog.heading.installEventFilter(observer)
            dialog.heading.update()
        observed.append((dialog.isVisible(), dialog.heading.text(),
                         dialog.detail.isVisible(), dialog.bar.isVisible(),
                         app.overrideCursor().shape()))
        if len(observed) == 1:
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        if len(observed) >= 8:
            release.set()
    timer = QTimer()
    timer.timeout.connect(inspect)
    timer.start(50)
    try:
        assert manager.run_background(work, mode, verb='Gitコミット', parent=owner) == 'completed'
    finally:
        timer.stop()
        release.set()
    assert len(observed) >= 8
    assert painted
    assert all(visible and 'Gitコミットしています' in text
               and detail == bar == (mode == PROGRESS)
               and cursor == Qt.CursorShape.WaitCursor
               for visible, text, detail, bar, cursor in observed)
    assert len({row[1] for row in observed}) > 1  # spinner keeps ticking
    assert app.overrideCursor() is None
    assert not dialogs[0].isVisible()


def test_fast_completion_and_original_failure(app, display):
    manager, dialogs, owner = display
    for n in range(10):
        assert manager.run_background(lambda: n, MESSAGE, verb='test', parent=owner) == n
    failure = ValueError('original')
    def work():
        raise failure
    with pytest.raises(ValueError) as caught:
        manager.run_background(work, MESSAGE, verb='test', parent=owner)
    assert caught.value is failure
    assert app.overrideCursor() is None and manager.depth == 0
