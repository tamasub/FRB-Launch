"""Launch's .lnk-free JSON-tracking contract (portable tests + Win integration)."""
from pathlib import Path
import os
import sys
import json
import subprocess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shell_link_stream import PREFIX, ShellLinkError, make_link_data, resolve_link_data
from launch_shell_tracking import (
    tracking_target_update, update_record_changes, matches_original_tracking)
from launch_menu_registration import records_for_sources


def _row(target, blob='TRACKED', *, title=None):
    return {'title': title if title is not None else Path(target).name,
            'description': str(target),
            'launch_shell_link_data': blob,
            'launch_actions': [{'launch_action_type': 'Open', 'launch_target': str(target),
                                'launch_arguments': [], 'launch_browser': ''}]}


def test_new_non_windows_entry_stays_legacy(tmp_path):
    f = tmp_path / '実験.txt'; f.write_text('testing', encoding='utf-8')
    record = records_for_sources([{'kind': 'file', 'value': str(f), 'title': f.name}])[0]
    assert record['launch_actions'][0]['launch_target'] == str(f)
    if os.name != 'nt':
        assert 'launch_shell_link_data' not in record


def test_original_target_exists_does_not_search_or_write(tmp_path):
    f = tmp_path / 'original.txt'; f.write_text('original')
    row = _row(f)
    def bad_search(_): raise AssertionError('tracking must not run on existing path')
    assert tracking_target_update(row, resolver=bad_search) is None


def test_rename_tracking_updates_path_and_automatic_title(tmp_path):
    old = tmp_path / '元の名前.txt'
    new = tmp_path / '変更後.txt'; new.write_text('same file')
    record = _row(old)
    new_path, blob = tracking_target_update(record, resolver=lambda _: (str(new), 'UPDATED'))
    assert (new_path, blob) == (str(new), 'UPDATED')
    changes = {x['path']: x['value'] for x in update_record_changes(record, new_path, blob)}
    assert changes['title'] == new.name
    assert changes['description'] == str(new)
    assert changes['launch_actions'][0]['launch_target'] == str(new)
    assert changes['launch_shell_link_data'] == 'UPDATED'
    assert record['title'] == old.name  # original record stays unchanged


def test_manual_title_is_preserved(tmp_path):
    old = tmp_path / 'a.txt'; new = tmp_path / 'b.txt'; new.write_text('B')
    record = _row(old, title='所長メモ')
    changed = {c['path']: c['value'] for c in update_record_changes(record, str(new), 'X')}
    assert 'title' not in changed


def test_original_studio_edit_guard(tmp_path):
    old = tmp_path / 'a.txt'; record = _row(old)
    assert matches_original_tracking(record, record)
    edited = _row(tmp_path / 'another.txt')
    assert not matches_original_tracking(edited, record)
    edited = _row(old, blob='OTHER')
    assert not matches_original_tracking(edited, record)


def test_untracked_and_special_actions_are_unaffected(tmp_path):
    path = tmp_path / 'gone.txt'; row = _row(path)
    assert tracking_target_update({**row, 'launch_shell_link_data': ''}) is None
    assert tracking_target_update({**row, 'launch_actions': [
        {'launch_action_type': 'Run', 'launch_program': 'python.exe'}]}) is None
    assert tracking_target_update({**row, 'launch_actions': [
        {'launch_action_type': 'Open', 'launch_target': str(path)},
        {'launch_action_type': 'Open', 'launch_target': str(path)}]}) is None


def test_broken_tracked_link_fails_closed(tmp_path):
    path = tmp_path / 'gone.txt'; record = _row(path)
    with pytest.raises(ShellLinkError):
        tracking_target_update(record, resolver=lambda _: ('/missing/file', 'DATA'))


def test_no_lnk_io_in_shell_stream_source():
    src = (Path(__file__).resolve().parents[1] / 'src/shell_link_stream.py').read_text()
    assert 'CreateStreamOnHGlobal' in src and 'IPersistStream.Save' in src
    assert 'IPersistFile' not in src
    assert 'os.startfile' not in src


@pytest.mark.skipif(os.name != 'nt', reason='Windows Shell COM integration')
def test_windows_roundtrip_rename_without_physical_lnk(tmp_path):
    old = tmp_path / '名前変更前.txt'; new = tmp_path / '名前変更後.txt'
    old.write_text('same', encoding='utf-8')
    blob = make_link_data(old)
    assert blob.startswith(PREFIX)
    blob = json.loads(json.dumps(blob))
    old.rename(new)
    target, updated = resolve_link_data(blob)
    assert os.path.samefile(target, new)
    assert updated.startswith(PREFIX)
    assert list(tmp_path.glob('*.lnk')) == []
