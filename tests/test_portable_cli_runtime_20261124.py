"""Portable dependency isolation: no real Windows executable needed for resolution."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from runtime_paths import resolve_node, resolve_studio_cli, portable_runtime
from launch_menu_registration import studio_core_root, _node_binary, RegistrationError
from launch_option_runtime import find_node, find_studio_root
import pytest


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('fixture', encoding='utf-8')
    return path


@pytest.mark.parametrize('layout', ['runtime/node/node.exe', 'Studio/runtime/node/node.exe'])
@pytest.mark.parametrize('external', [False, True])
def test_portable_both_bridges_choose_bundled_node(tmp_path, layout, external):
    home = tmp_path / 'Launch'
    touch(home / 'installed_release.json')
    node = touch(home / layout)
    studio = home / 'Studio'
    touch(studio / 'tools/change_core/cli.mjs')
    touch(studio / 'tools/option_settings/cli.mjs')
    touch(home / 'defs/launch/frb_launch_maintenance_view_def_v0_1.json')
    old = tmp_path / 'FRB_Studio'
    touch(old / 'tools/change_core/cli.mjs')
    touch(old / 'tools/option_settings/cli.mjs')
    outside = touch(tmp_path / 'external/node.exe') if external else None
    with patch('runtime_paths.shutil.which', return_value=str(outside) if outside else None) as which, \
         patch.dict('os.environ', {'FRB_LAUNCH_NODE': str(outside) if outside else ''}):
        assert studio_core_root(home, old) == studio
        assert find_studio_root(home, old) == studio
        assert _node_binary(studio, home) == str(node)
        assert find_node(home, studio) == str(node)
        which.assert_not_called()


def test_portable_never_falls_back(tmp_path):
    home = tmp_path / 'Launch'
    touch(home / 'installed_release.json')
    old = tmp_path / 'FRB_Studio'
    touch(old / 'tools/change_core/cli.mjs')
    touch(old / 'tools/option_settings/cli.mjs')
    outside = touch(old / 'runtime/node/node.exe')
    touch(home / 'Studio/node.exe')  # obsolete workaround is not a shipped layout
    with patch('runtime_paths.shutil.which', return_value=str(outside)) as which, \
         patch.dict('os.environ', {'FRB_LAUNCH_NODE': str(outside)}):
        assert resolve_studio_cli(home, 'change_core', old) is None
        assert find_studio_root(home, old) is None
        assert find_node(home, old) is None
        with pytest.raises(RegistrationError, match='Node.js'):
            _node_binary(home / 'Studio', home)
        with pytest.raises(RegistrationError, match='同梱Studio'):
            _node_binary(old, home)
        which.assert_not_called()


def test_development_keeps_external_fallback(tmp_path):
    home = tmp_path / 'Launch'
    old = tmp_path / 'FRB_Studio'
    touch(old / 'tools/change_core/cli.mjs')
    outside = touch(tmp_path / 'external/node.exe')
    with patch('runtime_paths.shutil.which', return_value=str(outside)), \
         patch.dict('os.environ', {'FRB_LAUNCH_NODE': ''}):
        assert resolve_studio_cli(home, 'change_core') == old
        assert resolve_node(home, old) == str(outside)


def test_frozen_without_manifest_is_still_portable(tmp_path):
    exe = touch(tmp_path / 'FRBLaunch.exe')
    with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)):
        assert portable_runtime(tmp_path)
        touch(tmp_path / 'launch_home.json')
        assert not portable_runtime(tmp_path)
