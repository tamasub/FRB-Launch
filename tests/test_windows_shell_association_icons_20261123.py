"""Regression tests for Explorer-size icons and Windows file associations.

No Win32, GUI or PySide6 dependency on CI. On Windows, visually confirm that
.md uses the icon configured in Explorer, e.g. Obsidian when associated.
"""
import ast
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from file_icon_policy import icon_lookup, icon_source_path
import windows_file_association_icon as shell_icons


def launcher_row_icon():
    source = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    launcher = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                    and node.name == 'Launcher')
    method = next(node for node in launcher.body if isinstance(node, ast.FunctionDef)
                  and node.name == 'row_icon')
    scope = {'icon_lookup': icon_lookup, 'icon_source_path': icon_source_path, 'QFileInfo': lambda path: path,
             'Path': Path, 'icon': lambda name: ('default', name)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 'src/app.py', 'exec'), scope)
    return scope['row_icon']


def test_files_panels_match_explorer_small_icon_dimensions():
    source = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    class_body = source.split('class ExpandedPanel(', 1)[1].split('class ExpandedLauncherView(', 1)[0]
    assert 'self.tree.setIconSize(QSize(16, 16))' in class_body
    assert 'self.tree.setIconSize(QSize(19, 19))' not in class_body


def test_shell_association_used_first_for_md_and_cached(monkeypatch):
    call = []
    class FakeIcon:
        def isNull(self):
            return False
    obsidian = FakeIcon()
    fake_shell = types.SimpleNamespace(file_type_icon=lambda extension, size, file_path=None:
        (call.append((extension, size, file_path)), obsidian)[1])
    monkeypatch.setitem(sys.modules, 'windows_file_association_icon', fake_shell)
    class Provider:
        def icon(self, target):
            raise AssertionError('Shell icon should take priority over Qt sample')
    class Launcher:
        file_icons = Provider()
        icon_cache = {}
    row = {'icon_key': 'file', 'item_kind': 'virtual_launch_file',
           'launch_actions': [{'launch_action_type': 'Open',
                               'launch_target': r'C:\Notes\FRB.md'}]}
    render = launcher_row_icon()
    assert render(Launcher, row) is obsidian
    assert render(Launcher, row) is obsidian
    assert call == [('.md', 16, r'C:\Notes\FRB.md')]
    assert row['launch_actions'][0]['launch_target'] == r'C:\Notes\FRB.md'


def test_missing_shell_icon_retains_qt_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules, 'windows_file_association_icon',
                        types.SimpleNamespace(file_type_icon=lambda *args, **kwargs: None))
    queried = []
    class FakeIcon:
        def isNull(self):
            return False
    qt_icon = FakeIcon()
    class Provider:
        def icon(self, info):
            queried.append(info)
            return qt_icon
    class Launcher:
        file_icons = Provider()
        icon_cache = {}
    render = launcher_row_icon()
    file_row = {'icon_key': 'file', 'item_kind': 'command', '_file': r'F:\Notes\Book.xlsx'}
    assert render(Launcher, file_row) is qt_icon
    assert queried == ['FRBLaunchTypeSample.xlsx']


def test_native_icon_resolver_safe_on_non_windows():
    if shell_icons.os.name != 'nt':
        assert shell_icons.file_type_icon('.md') is None
        assert shell_icons.file_type_icon('.xlsx') is None
    assert shell_icons.file_type_icon('file.md') is None


def test_native_icon_source_uses_shell_extension_attribute_flag_and_destroys_hicon():
    source = (ROOT / 'src/windows_file_association_icon.py').read_text(encoding='utf-8')
    assert 'shell.SHGetFileInfoW(path, 0x80 if use_file_attributes else 0,' in source
    assert '_SHGFI_ICON = 0x100' in source and '_SHGFI_USEFILEATTRIBUTES = 0x10' in source
    assert 'DestroyIcon(info.hIcon)' in source and 'DestroyIcon(small)' in source
    assert 'DeleteObject(bitmap)' in source
    assert 'DeleteDC(dc)' in source
    assert 'QImage.Format.Format_ARGB32_Premultiplied' in source
