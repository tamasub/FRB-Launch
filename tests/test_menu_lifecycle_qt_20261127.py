"""Native Qt verification (Windows acceptance still required for focus/IME)."""
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6.QtWidgets')
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from menu_lifecycle import install_terminal_menu


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_late_submenu_leaf_mouse_closes_before_callback(app):
    root = QMenu()
    root.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
    install_terminal_menu(root)  # settings menus are populated after wiring
    submenu = root.addMenu('New')
    leaf = submenu.addAction('Folder')
    seen = []
    leaf.triggered.connect(lambda checked=False: seen.append(
        (root.isVisible(), submenu.isVisible(), app.overrideCursor().shape())))
    root.popup(QPoint(20,20)); app.processEvents()
    submenu.popup(QPoint(150,20)); app.processEvents()
    assert root.isVisible() and submenu.isVisible()
    QTest.mouseClick(submenu, Qt.MouseButton.LeftButton, pos=submenu.actionGeometry(leaf).center())
    assert seen == [(False, False, Qt.CursorShape.WaitCursor)]
    assert app.overrideCursor() is None
    root.deleteLater()


def test_enter_and_reopen_persistent_menu(app):
    root = QMenu()
    root.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
    leaf = root.addAction('Command')
    events = []
    leaf.triggered.connect(lambda checked=False: events.append(root.isVisible()))
    install_terminal_menu(root)
    for _ in range(2):
        root.popup(QPoint(20,20)); app.processEvents()
        root.setActiveAction(leaf)
        QTest.keyClick(root, Qt.Key.Key_Return)
        assert not root.isVisible()
    assert events == [False,False]
    root.deleteLater()
