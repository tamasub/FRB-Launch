"""Static checks, not a substitute for a Windows GUI run."""
from pathlib import Path
import re

OUT = Path(__file__).resolve().parents[1]


def read(name):
    return (OUT / name).read_text(encoding='utf-8-sig')


def test_gui_uses_builtin_winforms_not_tkinter_or_pyinstaller():
    s = read('release_FRBLaunch_GUI.ps1')
    assert 'System.Windows.Forms' in s and 'Yu Gothic UI' in s
    assert 'tkinter' not in s.lower() and 'pyinstaller' not in s.lower()


def test_gui_version_from_gh_releases_with_patch_default():
    s = read('release_FRBLaunch_GUI.ps1')
    assert 'gh.exe' in s and 'release list --repo' in s and '--json tagName,isDraft' in s
    assert 'if ([bool]$draftProp.Value) { continue }' in s
    assert 'NextVersion $script:LatestRemote' in s
    assert '$script:kind.SelectedIndex=0' in s
    assert "'Patch'" in s and "'Minor'" in s and "'Major'" in s


def test_gui_does_not_publish_without_preparation_and_click_confirmation():
    s = read('release_FRBLaunch_GUI.ps1')
    assert "BeginJob 'PREPARE'" in s
    assert "BeginJob 'PUBLISH'" in s
    assert '$script:PreparedVersion -cne $script:SelectedVersion' in s
    assert 'MessageBoxButtons]::YesNo' in s
    assert 'DialogResult]::Yes' in s
    assert ' -PublishOnly -GuiApprovedTag ' in s
    assert "if ($type -eq 'PREPARE')" in s and "-PrepareOnly'" in s


def test_gui_preparation_stops_if_remote_version_unknown():
    s = read('release_FRBLaunch_GUI.ps1')
    assert "BeginJob 'DISCOVER_FEED'" in s
    assert 'Preview Feed' in s
    assert '$script:RemoteReady=$false' in s
    assert '$script:prepare.Enabled = (-not $busy -and $script:RemoteReady)' in s


def test_cli_still_requires_explicit_human_approval_in_default_flow():
    s = read('release_FRBLaunch_GitHub.ps1')
    assert '[string]$GuiApprovedTag' in s
    assert 'if (-not $PublishOnly)' in s
    assert '$approved = Read-Host' in s
    assert "$approved -cne ('PUBLISH ' + $tag)" in s
    assert "Invoke-ReleaseStep 'publish'" in s


def test_cli_remains_ascii_crlf_ps51_safe():
    raw=(OUT/'release_FRBLaunch_GitHub.ps1').read_bytes()
    assert raw.isascii()
    assert raw.count(b'\r\n') == raw.count(b'\n')


def test_utf8_bom_and_crlf_for_japanese_ps51_gui():
    raw=(OUT/'release_FRBLaunch_GUI.ps1').read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf')
    assert raw.count(b'\r\n') == raw.count(b'\n')


def test_launchers_always_use_local_ps_file():
    vbs=read('FRB_Release_Manager.vbs')
    bat=read('FRB_Release_Manager_debug.bat')
    assert 'release_FRBLaunch_GUI.ps1' in vbs and '-STA' in vbs
    assert 'release_FRBLaunch_GUI.ps1' in bat and '-STA' in bat


def test_gui_never_calls_git_publish_command_directly():
    s=read('release_FRBLaunch_GUI.ps1')
    assert 'gh release create' not in s and 'gh release upload' not in s
    assert ' -ConfigureTestInstall' not in s
    assert 'release_FRBLaunch_GitHub.ps1' in s
