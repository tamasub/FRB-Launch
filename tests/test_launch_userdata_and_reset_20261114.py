"""UserData owner contract: byte-for-byte migration, Studio path, reset backup."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from launch_config_path import CONFIG_NAME, ensure_launch_config
from launch_data_reset import reset_launch_data, BACKUP_ENTRY
from launch_menu_registration import launch_view_def_path


def _json(text):
    return (json.dumps({'title': text, 'pages': [], 'items': []}, ensure_ascii=False) + '\n').encode('utf8')


def _fixture(tmp_path):
    home = tmp_path / 'FRB_Apps' / 'FRB_Launch'
    (home / 'config').mkdir(parents=True)
    (home / 'defaults').mkdir()
    state = tmp_path / 'LocalAppData' / 'FRBLaunch'
    return home, state


def test_template_uses_exact_latest_full_user_data():
    template = ROOT / 'defaults/frb_launch_data.template.json'
    data = json.loads(template.read_text('utf-8-sig'))
    assert isinstance(data.get('pages'), list) and isinstance(data.get('items'), list)
    legacy = ROOT / 'config/frb_launch_data.json'
    # After UserData migration, source-backup ZIPs intentionally omit the
    # former user-owned config. The approved template remains the seed.
    if legacy.exists():
        assert template.read_bytes() == legacy.read_bytes()



def test_first_migration_prefers_existing_user_json_over_system(tmp_path):
    home, state = _fixture(tmp_path)
    old = _json('user maintained')
    (home / 'config' / CONFIG_NAME).write_bytes(old)
    (home / 'defaults/frb_launch_data.template.json').write_bytes(_json('template'))
    user = ensure_launch_config(home, user_root=state/'UserData')
    assert user == state/'UserData'/CONFIG_NAME
    assert user.read_bytes() == old
    assert (home/'config'/CONFIG_NAME).read_bytes() == old
    user.write_bytes(_json('studio-edited'))
    (home/'config'/CONFIG_NAME).write_bytes(_json('overwritten by update'))
    assert ensure_launch_config(home, user_root=state/'UserData') == user
    assert user.read_bytes() == _json('studio-edited')


def test_fresh_install_uses_template_when_config_is_absent(tmp_path):
    home, state = _fixture(tmp_path)
    expected = _json('from template')
    (home / 'defaults/frb_launch_data.template.json').write_bytes(expected)
    assert ensure_launch_config(home, user_root=state/'UserData').read_bytes() == expected


def test_corrupt_user_json_fails_closed_without_overwriting(tmp_path):
    home, state = _fixture(tmp_path)
    (home/'defaults/frb_launch_data.template.json').write_bytes(_json('template'))
    user=state/'UserData'/CONFIG_NAME
    user.parent.mkdir(parents=True)
    user.write_bytes(b'{invalid')
    with pytest.raises(ValueError, match='JSON'):
        ensure_launch_config(home, user_root=state/'UserData')
    assert user.read_bytes() == b'{invalid'


def test_launch_viewdef_is_owned_by_launch_even_when_user_json_is_appdata(tmp_path, monkeypatch):
    home, state = _fixture(tmp_path)
    monkeypatch.setenv('FRB_LAUNCH_HOME', str(home))
    user = state/'UserData'/CONFIG_NAME
    assert launch_view_def_path(user) == home/'defs/launch/frb_launch_maintenance_view_def_v0_1.json'
    monkeypatch.delenv('FRB_LAUNCH_HOME')
    with pytest.raises(ValueError, match='FRB_LAUNCH_HOME'):
        launch_view_def_path(user)


def test_reset_uses_only_existing_backup_and_restores_exact_template(tmp_path):
    home, state = _fixture(tmp_path)
    user=state/'UserData'/CONFIG_NAME
    user.parent.mkdir(parents=True)
    original=_json('current user')
    template=_json('template exact')
    user.write_bytes(original)
    (home/'defaults/frb_launch_data.template.json').write_bytes(template)
    (home/'backup_frb_launch_config_log.bat').write_text('fake bat',encoding='utf8')

    def backup():
        d=state/'_Backups'
        d.mkdir()
        with ZipFile(d/'FRBLaunch_Backup_test.zip','w') as z:
            z.writestr(BACKUP_ENTRY,original)

    result=reset_launch_data(home,state,run_backup=backup)
    assert result.name == 'FRBLaunch_Backup_test.zip'
    assert user.read_bytes() == template
    assert (state/'_Backups'/result.name).exists()


def test_reset_aborts_when_existing_backup_missing_userdata(tmp_path):
    home,state=_fixture(tmp_path)
    user=state/'UserData'/CONFIG_NAME
    user.parent.mkdir(parents=True)
    old=_json('original')
    user.write_bytes(old)
    (home/'defaults/frb_launch_data.template.json').write_bytes(_json('template'))
    (home/'backup_frb_launch_config_log.bat').write_text('fake bat',encoding='utf8')

    def backup():
        d=state/'_Backups'
        d.mkdir()
        with ZipFile(d/'FRBLaunch_Backup_test.zip','w') as z:
            z.writestr('config/frb_launch_data.json',old)

    with pytest.raises(RuntimeError,match='対象のUser設定'):
        reset_launch_data(home,state,run_backup=backup)
    assert user.read_bytes() == old


def test_reset_aborts_if_studio_changes_data_during_backup(tmp_path):
    home,state=_fixture(tmp_path)
    user=state/'UserData'/CONFIG_NAME
    user.parent.mkdir(parents=True)
    old=_json('original')
    user.write_bytes(old)
    (home/'defaults/frb_launch_data.template.json').write_bytes(_json('template'))
    (home/'backup_frb_launch_config_log.bat').write_text('fake bat',encoding='utf8')

    def backup():
        d=state/'_Backups';d.mkdir()
        with ZipFile(d/'FRBLaunch_Backup_test.zip','w') as z:
            z.writestr(BACKUP_ENTRY,old)
        user.write_bytes(_json('Studio saved a new value'))

    with pytest.raises(RuntimeError,match='Studio'):
        reset_launch_data(home,state,run_backup=backup)
    assert user.read_bytes() == _json('Studio saved a new value')


def test_source_and_studio_bridge_contract():
    launch=(ROOT/'src/app.py').read_text('utf8')
    assert "user_root=STATE / 'UserData'" in launch
    assert "'--launch-home='" in launch
    assert 'FRB_LAUNCH_HOME' in launch
    assert 'UserData' in (ROOT/'scripts/Backup-FrbLaunch.ps1').read_text('utf8')


def test_appdata_user_json_is_the_only_changeset_commit_target(tmp_path, monkeypatch):
    """Real Node ChangeSet: source config and Launch ViewDef stay unchanged."""
    import shutil
    from launch_menu_registration import commit_add, category_record
    studio_root=Path(os.environ.get('STUDIO_ROOT',ROOT.parent/'curr_studio_1114'))
    if not shutil.which('node') or not (studio_root/'tools/change_core/cli.mjs').is_file():
        pytest.skip('node/Studio source unavailable')
    home, state=_fixture(tmp_path)
    source=ROOT/'defaults/frb_launch_data.template.json'
    (home/'config/frb_launch_data.json').write_bytes(source.read_bytes())
    viewfile=home/'defs/launch/frb_launch_maintenance_view_def_v0_1.json'
    viewfile.parent.mkdir(parents=True)
    viewfile.write_bytes((ROOT/'defs/launch/frb_launch_maintenance_view_def_v0_1.json').read_bytes())
    user=ensure_launch_config(home,user_root=state/'UserData')
    original_system=(home/'config/frb_launch_data.json').read_bytes()
    original_view=viewfile.read_bytes()
    monkeypatch.setenv('FRB_LAUNCH_HOME',str(home))
    result=commit_add(user,studio_root,'work','',[category_record('AppDataで追加した項目')])
    assert result['status']=='COMMITTED'
    assert (home/'config/frb_launch_data.json').read_bytes()==original_system
    assert viewfile.read_bytes()==original_view
    user_rows=json.loads(user.read_text('utf8'))['items']
    assert any(row.get('title')=='AppDataで追加した項目' for row in user_rows)
