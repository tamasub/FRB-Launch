"""Inspector TOPMOST forensic fields remain read-only and exportable.

PowerShell 5.1 and real GUI sampling require Windows; this checks the stable
collector/report contract without pretending to simulate desktop composition.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'tools/FRB_Window_Inspector/collect_windows.ps1').read_text(encoding='utf-8-sig')


def test_ws_ex_topmost_is_derived_from_extended_style_for_all_windows():
    assert 'Topmost = (([Convert]::ToUInt32(' in SCRIPT
    assert 'LongHex($handle, -20)).Substring(2), 16) -band 0x8)' in SCRIPT
    assert 'ExStyle = [FRBWindowInspectorNative]::LongHex($handle, -20)' in SCRIPT


def test_shared_timeline_records_actual_neighbor_topmost_and_overlap():
    for field in (
        'NearestVisibleAboveTopmost', 'NearestVisibleAboveExStyle',
        'NearestOverlappingAboveHWND', 'NearestOverlappingAboveProcess',
        'NearestOverlappingAboveTopmost', 'NearestOverlappingAboveExStyle',
        'AboveCursorTopmost', 'ForegroundTopmost', 'Topmost = $w.Topmost',
    ):
        assert field in SCRIPT
    assert 'NearestOverlappingAboveProcess = $(if ($null -ne $overlapping)' in SCRIPT
    assert 'zorder_timeline_FOCUS.csv' in SCRIPT


def test_no_window_reordering_or_new_privileged_capture():
    for forbidden in ('SetWindowPos', 'SetForegroundWindow', 'SetParent(', 'AttachThreadInput'):
        assert forbidden not in SCRIPT
    assert '$shareFiles = @(' in SCRIPT
    assert 'windows_FOCUS.csv' in SCRIPT
    assert 'FRB_WindowReport_FOCUS_SHARE.zip' in SCRIPT
