"""Contract tests for FRB Launch GitHub Release discovery compatibility.

Note: PowerShell 5.1 execution is covered by the adjacent .ps1 test on Windows.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'release_FRBLaunch_GUI.ps1'


def test_fixture_matches_reported_repro():
    items = json.loads('[{"isDraft":false,"tagName":"v0.9.8"}]')
    assert len(items) == 1
    assert items[0]['isDraft'] is False and items[0]['tagName'] == 'v0.9.8'


def test_release_rows_are_flattened_before_field_inspection():
    text = GUI.read_text(encoding='utf-8-sig')
    assert 'function Expand-ReleaseRows([object]$item)' in text
    assert 'if ($item -is [System.Array])' in text
    assert 'foreach ($child in $item) { Expand-ReleaseRows $child }' in text
    assert 'function Get-ReleaseVersions([string]$rawJson)' in text
    assert 'foreach ($r in @(Expand-ReleaseRows $parsed))' in text
    assert '$versions = @(Get-ReleaseVersions $stdout)' in text
    assert '$rows = @(ConvertFrom-Json' not in text


def test_existing_safety_rules_preserved():
    text = GUI.read_text(encoding='utf-8-sig')
    assert "if ($versions.Count -eq 0)" in text
    assert "BeginJob 'DISCOVER_FEED'" in text
    assert "Sort-Object { VersionCode $_ } -Descending" in text
    assert "if ([bool]$draftProp.Value) { continue }" in text
    assert "if ($tag -match '^v(\\d+\\.\\d+\\.\\d+)$')" in text
    assert "BeginJob 'PREPARE'" in text
    assert "BeginJob 'PUBLISH'" in text
    assert ' -PublishOnly -GuiApprovedTag ' in text
    assert "[System.Windows.Forms.MessageBoxButtons]::YesNo" in text


def test_ps51_gui_encoding_preserved():
    data = GUI.read_bytes()
    assert data.startswith(b'\xef\xbb\xbf')
    assert data.count(b'\r\n') == data.count(b'\n')
