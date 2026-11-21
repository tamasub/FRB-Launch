"""Release gates for the Obsidian / VSCode / Sakura / Studio invitations."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from launch_state_defaults import ensure_initial_state_ini
from third_column_host_options import embedded_editor_enabled
import vscode_guest_bridge as vs
import sakura_guest_bridge as sa
from obsidian_ime_overlay import overlay_enabled


def test_first_install_seeds_desired_invitation_flags(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    current = tmp_path / 'FRBLaunch' / 'state.ini'
    ensure_initial_state_ini(ROOT / 'defaults' / 'state.ini', current)
    for editor in ('studio', 'obsidian', 'vscode'):
        assert embedded_editor_enabled(None, editor)
    assert not embedded_editor_enabled(None, 'sakura')
    assert vs.enabled() and not sa.enabled()
    monkeypatch.delenv('FRB_OBSIDIAN_IME_OVERLAY', raising=False)
    assert overlay_enabled()


def test_user_state_is_authoritative_over_trial_flags(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    ini = tmp_path / 'FRBLaunch' / 'state.ini'
    ini.parent.mkdir()
    ini.write_text('[General]\nembed_vscode=false\nembed_sakura=false\nembed_obsidian=false\nembed_studio=true\n', encoding='utf-8')
    original = ini.read_bytes()
    monkeypatch.setenv('FRB_VSCODE_GUEST_OVERLAY', '1')
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    assert not vs.enabled() and not sa.enabled()
    assert not embedded_editor_enabled(None, 'obsidian')
    monkeypatch.setenv('FRB_OBSIDIAN_IME_OVERLAY', '1')
    assert not overlay_enabled()
    ensure_initial_state_ini(ROOT / 'defaults' / 'state.ini', ini)
    assert ini.read_bytes() == original  # Explicit existing user choices never overwritten


def test_vscode_flag_is_separate_from_studio_and_sakura(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    ini = tmp_path / 'FRBLaunch' / 'state.ini'
    ini.parent.mkdir()
    ini.write_text('[General]\nembed_vscode=true\nembed_studio=false\nembed_sakura=false\n', encoding='utf-8')
    monkeypatch.delenv('FRB_VSCODE_GUEST_OVERLAY', raising=False)
    assert vs.enabled()
    assert not embedded_editor_enabled(None, 'studio')
    assert not sa.enabled()


def test_distribution_template_is_single_source_of_initial_editor_flags(tmp_path):
    template = tmp_path / 'defaults' / 'state.ini'
    template.parent.mkdir()
    template.write_text('[General]\nembed_studio=false\nembed_obsidian=false\n'
                        'embed_vscode=false\nembed_sakura=true\n', encoding='utf-8')
    created = tmp_path / 'per_user' / 'state.ini'
    ensure_initial_state_ini(template, created)
    initial = created.read_text('utf-8')
    for key, value in (('embed_studio','false'), ('embed_obsidian','false'),
                       ('embed_vscode','false'), ('embed_sakura','true')):
        assert f'{key}={value}' in initial
