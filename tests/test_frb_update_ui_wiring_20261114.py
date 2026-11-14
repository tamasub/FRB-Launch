"""Static UI contract for environments without Windows Qt installed."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'src/app.py').read_text('utf-8')
ui=(ROOT/'src/update_information_dialog.py').read_text('utf-8')

def test_update_action_is_separate_from_legacy_about_and_nonmodal():
    assert "addAction('バージョンアップ情報...')" in app
    assert "self.theme_update_action.triggered.connect(self.show_update_information)" in app
    assert "self.theme_about_action.triggered.connect(self.show_version_information)" in app
    assert 'dialog.show()' in app
    assert 'dialog.exec()' not in app
    assert 'self.setModal(False)' in ui

def test_user_click_gates_update_process_and_dev_folder_is_protected():
    assert 'self.check.clicked.connect(self.check_latest)' in ui
    assert 'self.apply.clicked.connect(self.start_update)' in ui
    assert 'self.apply.setEnabled(False)' in ui
    assert "(self.install_root/'launch_home.json').exists()" in ui
    assert "self._can_apply()" in ui
