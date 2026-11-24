"""Read-only .md document icon priority for real and JSON-dropped files.

These tests don't need a Windows desktop; native rendering requires the user's PC.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from file_icon_policy import icon_lookup, icon_source_path
from windows_file_association_icon import (
    _choose_icon, _split_icon_reference, _ASSOCSTR_DEFAULTICON, _ASSOCSTR_EXECUTABLE,
)


def test_defaulticon_wins_over_generic_and_real_path():
    calls = []
    ob = object()
    def assoc(ext, kind):
        calls.append(('association', ext, kind))
        return r'C:\Users\Test\AppData\Local\Programs\Obsidian\Obsidian.exe,-2'
    def resource(ref):
        calls.append(('resource', ref))
        return ob
    def shell(path, attrs):
        raise AssertionError('no fallback after registered document resource')
    result = _choose_icon('.md', r'F:\Notes\memo.md', assoc, resource, shell)
    assert result is ob
    assert calls[0] == ('association', '.md', _ASSOCSTR_DEFAULTICON)
    assert len(calls) == 2


def test_real_path_is_used_if_registered_icon_is_not_extractable():
    calls = []
    expected = object()
    result = _choose_icon(
        '.md', r'F:\Notes\memo.md',
        lambda *a: r'C:\Missing\icon.dll,-10',
        lambda ref: None,
        lambda path, fake: (calls.append((path, fake)), expected)[1])
    assert result is expected
    assert calls == [(r'F:\Notes\memo.md', False)]


def test_obsidian_executable_icon_fallback_only_when_effective_default():
    calls = []
    exe = r'C:\Users\Test\AppData\Local\Programs\Obsidian\Obsidian.exe'
    expected = object()
    result = _choose_icon(
        '.md', None,
        lambda _ext, kind: exe if kind == _ASSOCSTR_EXECUTABLE else None,
        lambda _: None,
        lambda path, attrs: (calls.append((path, attrs)), expected)[1])
    assert result is expected
    assert calls == [(exe, False)]


def test_another_default_app_is_never_disguised_as_obsidian():
    calls = []
    def assoc(_ext, kind):
        return r'C:\Program Files\Microsoft VS Code\Code.exe' if kind == _ASSOCSTR_EXECUTABLE else None
    expected = object()
    result = _choose_icon('.md', None, assoc, lambda ref: None,
                          lambda path, attrs: (calls.append((path, attrs)), expected)[1])
    assert result is expected
    assert calls == [('.md', True)]


def test_non_md_file_types_keep_old_single_shell_extension_behavior():
    calls = []
    for extension in ('.txt', '.xlsx', '.json', '.pdf'):
        assert _choose_icon(extension, 'C:\\fake', lambda *args: 1,
                            lambda ref: 'not used',
                            lambda path, attrs: calls.append((path, attrs)) or 'type') == 'type'
    assert calls == [(ext, True) for ext in ('.txt', '.xlsx', '.json', '.pdf')]


def test_failures_fall_back_without_crashing():
    events = []
    def broken(*_args):
        events.append('failed')
        raise OSError('Shell unavailable')
    assert _choose_icon('.md', 'F:\\missing.md', broken, broken, broken) is None
    assert len(events) >= 3


def test_icon_reference_positive_negative_and_bad_inputs():
    assert _split_icon_reference(r'C:\Apps\Obsidian\Obsidian.exe,-2') == (
        r'C:\Apps\Obsidian\Obsidian.exe', -2)
    assert _split_icon_reference(r'"C:\Program Files\Obsidian\app.ico",0') == (
        r'C:\Program Files\Obsidian\app.ico', 0)
    assert _split_icon_reference(r'C:\Apps\Obsidian\Obsidian.exe') == (
        r'C:\Apps\Obsidian\Obsidian.exe', 0)
    assert _split_icon_reference('invalid') is None
    assert _split_icon_reference('C:\\bad.dll,NaN') is None


def test_files_exp_and_imported_json_md_preserve_identity_and_custom_icons():
    file_row = {'_file': r'F:\FRB\memo.md', 'icon_key': 'file'}
    json_row = {'icon_key': 'file', 'item_kind': 'virtual_launch_file',
                'launch_actions': [{'launch_action_type': 'Open',
                                    'launch_target': r'F:\FRB\memo.md'}]}
    before = repr(json_row)
    for row in (file_row, json_row):
        assert icon_lookup(row) == ('type', '.md')
        assert icon_source_path(row) == r'F:\FRB\memo.md'
    assert repr(json_row) == before
    assert '_file' not in json_row
    assert icon_lookup({**json_row, 'icon_key': 'custom'}) == ('default', 'custom')
