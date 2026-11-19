"""Sakura non-parenting guest feature gate and safe HWND selection."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import sakura_guest_bridge as guest


def test_disabled_by_default():
    assert not guest.enabled({})
    assert guest.enabled({'FRB_SAKURA_GUEST_OVERLAY': '1'})
    assert not guest.enabled({'FRB_SAKURA_GUEST_OVERLAY': '0'})


def test_new_handle_and_filename_required():
    items = [(10, 100, 'report.txt - サクラエディタ'),
             (20, 200, 'report.txt - サクラエディタ')]
    assert guest.new_hwnd_for_file(items, frozenset({10}), 'C:/temp/report.txt') == 20
    assert guest.new_hwnd_for_file(items, frozenset({10, 20}), 'C:/temp/report.txt') is None
    assert guest.new_hwnd_for_file(items, frozenset(), 'C:/temp/wrong.txt') is None
    assert guest.new_hwnd_for_file(items, frozenset(), 'C:/temp/report.txt') is None


def test_japanese_filename_caption():
    assert guest.caption_matches_file('検証ログ.txt - サクラエディタ', 'C:/文書/検証ログ.txt')


def test_trial_launcher_sets_only_environment_flags():
    launch = (ROOT / '_run_windows_Try_Sakura_Overlay.bat').read_text()
    assert 'FRB_SAKURA_GUEST_OVERLAY=1' in launch
    assert 'call _run_windows.bat' in launch
    assert 'state.ini' not in launch.splitlines()[-2]
