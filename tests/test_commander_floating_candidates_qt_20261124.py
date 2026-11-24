"""Real Qt regression: popup ownership, stationary search, mouse and key paths."""
import os
import pytest


def test_commander_search_anchor_and_external_tool(tmp_path):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget
    from commander.window import CommanderWindow

    app = QApplication.instance() or QApplication([])
    owner = QWidget()
    owner.show()
    script = tmp_path / 'example.ps1'
    script.write_text('param()\n', encoding='utf-8')
    definition = {
        'title': '選択テスト',
        'steps': [{'id': 'source', 'input': 'single_choice',
                   'label': '比較方法', 'choices': [
                       {'label': '未ステージ差分', 'value': 'working_tree'},
                       {'label': 'ステージ済み差分', 'value': 'staged'}]}],
    }
    window = CommanderWindow(owner, script, definition, tmp_path)
    try:
        window.show()
        app.processEvents()
        outer_before = window.geometry()
        status_before = window.status.mapToGlobal(QPoint(0, 0))
        assert not window.search.isVisible()
        QTest.mouseClick(window.crumb_buttons[0], Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window.geometry() == outer_before
        assert window.status.mapToGlobal(QPoint(0, 0)) == status_before
        assert window.candidate_popup.isWindow()
        assert window.candidate_popup.windowType() == Qt.WindowType.Tool
        assert window.candidate_popup.isVisible()
        assert window.search.isVisible()
        assert window.search.parent() is window.candidate_popup
        assert window.listbox.parent() is window.candidate_popup
        assert window.listbox.count() == 2
        popup_before = window.candidate_popup.geometry()
        editor_before = window.search.mapToGlobal(QPoint(0, 0))
        window.search.setText('済み')
        app.processEvents()
        assert window.listbox.count() == 1
        assert window.candidate_popup.geometry() == popup_before
        assert window.search.mapToGlobal(QPoint(0, 0)) == editor_before
        item_rect = window.listbox.visualItemRect(window.listbox.item(0))
        QTest.mouseClick(window.listbox.viewport(), Qt.MouseButton.LeftButton, pos=item_rect.center())
        app.processEvents()
        assert window.values['source'] == 'staged'
        assert not window.candidate_popup.isVisible()
        assert not window.search.isVisible()
        # Keyboard reopens the same popup; Esc closes it without changing data.
        window.focus_breadcrumb()
        QTest.keyClick(window.breadcrumb_frame, Qt.Key.Key_Down)
        app.processEvents()
        assert window.candidate_popup.isVisible()
        QTest.keyClick(window.search, Qt.Key.Key_Escape)
        app.processEvents()
        assert not window.candidate_popup.isVisible()
        assert window.values['source'] == 'staged'
    finally:
        window.close()
        owner.close()


def test_text_popup_click_confirm_and_click_away(tmp_path):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QWidget
    from commander.window import CommanderWindow

    app = QApplication.instance() or QApplication([])
    owner = QWidget()
    definition = {'title': '入力', 'steps': [
        {'id': 'source', 'input': 'single_choice', 'label': '比較方法',
         'choices': [{'label': '範囲', 'value': 'range'}]},
        {'id': 'range', 'input': 'text', 'label': 'コミット範囲',
         'visible_when': {'source': 'range'}}]}
    window = CommanderWindow(owner, tmp_path / 'example.ps1', definition, tmp_path)
    try:
        window.values.update(source='range', range='main..HEAD')
        window.refresh_breadcrumbs()
        window.show()
        app.processEvents()
        QTest.mouseClick(window.crumb_buttons[1], Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window.focus_index == 1
        assert window.search.text() == 'main..HEAD'
        assert window.text_confirm.isVisible()
        assert not window.listbox.isVisible()
        window.search.setText('HEAD~2..HEAD')
        QTest.mouseClick(window.text_confirm, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window.values['range'] == 'HEAD~2..HEAD'
        assert not window.candidate_popup.isVisible()
        QTest.mouseClick(window.crumb_buttons[1], Qt.MouseButton.LeftButton)
        app.processEvents()
        window.search.setText('discard')
        QTest.mouseClick(window.hint, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert not window.candidate_popup.isVisible()
        assert window.values['range'] == 'HEAD~2..HEAD'
    finally:
        window.close()
        owner.close()
