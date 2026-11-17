"""Protect the PS 5.1 wrapper against null/empty Join-Path -Path."""
from pathlib import Path

WRAPPER = Path(__file__).parents[1] / 'release_FRBLaunch_GitHub.ps1'


def test_source_root_is_not_resolved_during_parameter_binding():
    script = WRAPPER.read_text('ascii')
    assert "[string]$LaunchSource = ''" in script
    assert '[string]$LaunchSource = $PSScriptRoot' not in script
    assert '$MyInvocation.MyCommand.Path' in script
    assert '$LaunchSource = Split-Path -Path $entryPath -Parent' in script


def test_launch_source_is_checked_before_any_path_join():
    script = WRAPPER.read_text('ascii')
    assert script.index('IsNullOrWhiteSpace($LaunchSource)') < script.index('$python = Join-Path $LaunchSource')
    assert script.index('Test-Path -LiteralPath $LaunchSource -PathType Container') < script.index('$python = Join-Path $LaunchSource')
    assert 'Specify -LaunchSource' in script


def test_release_safety_and_original_arguments_unchanged():
    script = WRAPPER.read_bytes()
    assert script.isascii()
    assert script.count(b'\r\n') == script.count(b'\n')
    assert b'[switch]$PrepareOnly' in script
    assert b'[switch]$PublishOnly' in script
    assert b'[switch]$ConfigureTestInstall' in script
    assert b'Read-Host' in script and b'PUBLISH ' in script
    assert b"Invoke-ReleaseStep 'publish' @('--approved-tag', $tag)" in script
