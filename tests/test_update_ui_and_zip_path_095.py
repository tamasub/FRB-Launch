"""0.9.5 UI and local ZIP command invariants, runnable without Windows Qt."""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from core import Expander
from repair_exp_development_roots import plan_repair
from frb_update.progress_ui import STAGE_NAMES, bar_display

APP = (ROOT / 'src/app.py').read_text('utf-8')
DIALOG = (ROOT / 'src/update_information_dialog.py').read_text('utf-8')


def source_data():
    return json.loads((ROOT / 'defaults/frb_launch_data.template.json').read_text('utf-8'))


def test_zip_commands_explicitly_reference_development_sources():
    d = source_data()
    x = Expander(d, values={'launch_home': r'F:\FRB_Update_Test\FRBLaunch',
                            'studio_root': r'F:\FRB_Update_Test\FRBLaunch\Studio'})
    items = {row['item_id']: row for row in d['items']}
    for ident in ('launch_source_zip', '410f2fb3-fc02-471f-8d45-a338e6096461',
                  '7b24abcd-77ef-49c4-8fc6-bbc49c2729a8'):
        assert x.expand(items[ident]['launch_actions'][0]['launch_target']) == r'F:\FRB_Apps\FRB_Launch\_make_launch_zip.bat'
    action = items['zip_studio']['launch_actions'][0]
    assert x.expand(action['launch_arguments'][2]) == r'F:\FRB_Apps\FRB_Studio\cmd_make_FRBStudio_App_zip_v2.bat'
    assert x.expand(action['launch_working_directory']) == r'F:\FRB_Apps\FRB_Studio'


def test_existing_userdata_repairs_known_legacy_zip_commands_only():
    d = source_data()
    items = {row['item_id']:row for row in d['items']}
    ids = ('launch_source_zip','410f2fb3-fc02-471f-8d45-a338e6096461','7b24abcd-77ef-49c4-8fc6-bbc49c2729a8')
    for ident in ids:
        items[ident]['launch_actions'][0]['launch_target'] = '%launch_home%\\_make_launch_zip.bat'
    action = items['zip_studio']['launch_actions'][0]
    action['launch_arguments'][2] = '%studio_root%\\cmd_make_FRBStudio_App_zip_v2.bat'
    action['launch_working_directory'] = '%studio_root%'
    custom = {'item_id':'own_item','launch_actions':[{'launch_action_type':'Open','launch_target':'%launch_home%\\_make_launch_zip.bat'}]}
    d['items'].append(custom)
    changes = plan_repair(d, r'F:\FRB_Apps\FRB_Launch', r'F:\FRB_Apps\FRB_Studio')
    assert len(changes) == 5
    assert custom['launch_actions'][0]['launch_target'] == '%launch_home%\\_make_launch_zip.bat'
    for ident in ids:
        assert items[ident]['launch_actions'][0]['launch_target'] == '%launch_source_root%\\_make_launch_zip.bat'
    assert action['launch_arguments'][2].startswith('%studio_source_root%')
    assert action['launch_working_directory'] == '%studio_source_root%'
    copy_after = copy.deepcopy(d)
    assert plan_repair(copy_after, r'F:\FRB_Apps\FRB_Launch', r'F:\FRB_Apps\FRB_Studio') == []


def test_update_is_opt_in_but_check_is_automatic():
    assert 'QTimer.singleShot(0, self.check_latest)' in DIALOG
    assert 'self.apply.clicked.connect(self.start_update)' in DIALOG
    assert 'self.apply.setEnabled(False)' in DIALOG
    assert 'self.checked_newer.emit(bool(newer))' in DIALOG
    assert 'QTimer.singleShot(2200, window.check_updates_quietly)' in APP
    assert "self.update_notice_button.clicked.connect(self.show_update_information)" in APP
    assert 'self.update_notice_button.hide()' in APP
    assert "QPushButton#headerUpdateNotice" in APP
    assert "self.version_notice_found.emit(newer)" in APP
    assert "self._set_update_notice" in APP
    assert 'start_update' not in APP[APP.index('def check_updates_quietly'):APP.index('def show_update_information')]


def test_version_dialog_and_readable_light_scheme():
    assert "self.setWindowTitle('FRB Launch — バージョン情報')" in DIALOG
    assert "addAction('バージョン情報...')" in APP
    assert "addAction('バージョンアップ情報...')" not in APP
    assert 'updateVersionValue' in DIALOG
    assert 'Yu Gothic UI' in DIALOG


def test_stage_language_and_progress_alignment():
    assert STAGE_NAMES['stage'] == '更新ファイルの展開（準備）'
    assert STAGE_NAMES['apply'] == 'インストール先への反映'
    assert bar_display('completed') == ('value', 1000)
    source = (ROOT / 'src/frb_update/progress_ui.py').read_text('utf-8')
    assert "'Yu Gothic UI'" in source
    assert "22, 181, 452, 24" in source
    assert "374, 216, 100, 29" in source
    assert 'WM_SETFONT' in source
