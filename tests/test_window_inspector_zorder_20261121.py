"""Static contract checks for the Windows-only FRB Window Inspector Z-order probe.

We cannot run Win32 GUI operations in Linux CI. These assertions instead prevent
regressions in the report shape and keep the existing Snapshot/Monitor entrypoints.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "tools" / "FRB_Window_Inspector"
PS = (INSPECTOR / "collect_windows.ps1").read_text(encoding="utf-8-sig")
BAT = (INSPECTOR / "FRB_Window_Inspector.bat").read_text(encoding="utf-8-sig")
README = (INSPECTOR / "README_使い方.md").read_text(encoding="utf-8-sig")


def test_existing_snapshot_and_monitor_operations_kept():
    assert "[ValidateSet('Snapshot', 'Monitor')]" in PS
    assert "[int]$IntervalMs = 250" in PS
    assert "-Mode Snapshot" in BAT
    assert "-Mode Monitor -DurationSeconds 30" in BAT
    assert "-Mode Monitor -DurationSeconds 60" in BAT


def test_zrank_comes_from_existing_read_only_top_window_enumeration():
    assert "foreach ($hwnd in [FRBWindowInspectorNative]::TopWindows())" in PS
    assert "New-WindowEntry $hwnd 'TopLevel' $processMap $zRank" in PS
    assert "ZRank = $zRank" in PS
    assert "public struct POINT" in PS
    assert "WindowFromPoint" in PS
    assert "GetCursorPos" in PS


def test_focus_timeline_captures_surrounding_window_and_actual_mouse_hit():
    required = (
        "Get-FocusedZOrderSamples",
        "NearestVisibleAboveHWND",
        "NearestVisibleAboveProcess",
        "AboveCursorHWND",
        "AboveCursorProcess",
        "HitRootHWND",
        "HitRootProcess",
        "ForegroundHWND",
        "ForegroundZRank",
        "zorder_timeline_FOCUS.csv",
    )
    for name in required:
        assert name in PS, name
    assert "$zOrderTimeline.Add($row)" in PS
    assert "Save-Csv $zOrderTimeline.ToArray()" in PS


def test_diagnostics_are_shareable_without_full_window_inventory():
    assert "'zorder_timeline_FOCUS.csv'" in PS.split("$shareFiles = @(", 1)[1]
    assert "ProcessName" in PS
    assert "NearestVisibleAboveClass" in PS
    assert "Snapshot" in README and "Monitor 30 seconds" in README
    assert "個人情報" in README
    assert "SetWindowPos" not in PS
    assert "SetForegroundWindow" not in PS
