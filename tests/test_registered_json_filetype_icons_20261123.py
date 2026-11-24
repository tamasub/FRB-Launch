"""A dropped JSON file uses the Windows-association icon in Files List.

Qt's native icon provider is verified separately on Windows. These tests exercise
real Launch virtual-row projection and actual Launcher.row_icon without Qt.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from file_icon_policy import icon_lookup, icon_source_path
from launch_menu_registration import records_for_sources
from launch_virtual_tree import virtual_launch_pages, virtual_list_rows


def _projection():
    sources = [
        {'kind': 'file', 'value': r'C:\Work\業務\Book1.xlsx', 'title': 'Book1.xlsx'},
        {'kind': 'file', 'value': r'C:\Work\業務\001_1.txt', 'title': '001_1.txt'},
        {'kind': 'file', 'value': r'C:\Work\業務\NOTE.MD', 'title': 'NOTE.MD'},
        {'kind': 'url', 'value': 'https://example.org/report.xlsx', 'title': 'Web report'},
        {'kind': 'directory', 'value': r'C:\Work\業務\Files', 'title': 'Files'},
    ]
    rows = records_for_sources(sources)
    for index, row in enumerate(rows):
        row.update(page_id='test', item_id=str(index), parent_item_id='', sort_order=index)
    page = virtual_launch_pages([{'page_id': 'test'}], rows)[0]
    return virtual_list_rows(page)


def test_dropped_files_are_resolved_from_json_open_action_not_virtual_file_path():
    rows = _projection()
    assert all('_file' not in r for r in rows)
    assert [icon_lookup(row) for row in rows[:3]] == [
        ('type', '.xlsx'), ('type', '.txt'), ('type', '.md')]
    assert icon_lookup(rows[3]) == ('default', 'globe')
    assert icon_lookup(rows[4]) == ('default', 'folder.yellow')
    # A linked directory retains its separately authored folder colour.
    assert rows[4]['icon_key'] == 'folder.yellow'
    assert rows[4]['item_kind'] == 'directory'


def test_json_is_unchanged_and_custom_icon_has_priority():
    row = {'item_kind': 'virtual_launch_file', 'icon_key': 'file',
           'launch_actions': [{'launch_action_type': 'Open',
                               'launch_target': r'D:\Notes\demo.txt'}]}
    original = repr(row)
    assert icon_lookup(row) == ('type', '.txt')
    assert repr(row) == original
    assert icon_lookup({**row, 'icon_key': 'archive'}) == ('default', 'archive')
    assert icon_lookup({**row, '_icon_file': r'C:\Program Files\MyApp\app.exe'}) == (
        'path', r'C:\Program Files\MyApp\app.exe')


def test_path_specific_file_kinds_do_not_convert_to_type_icons():
    for ext in ('.exe', '.lnk', '.ico', '.url', '.appref-ms'):
        path = r'C:\Apps\tool' + ext
        row = {'icon_key': 'file', 'item_kind': 'virtual_launch_file',
               'launch_actions': [{'launch_action_type': 'Open', 'launch_target': path}]}
        assert icon_lookup(row) == ('path', path)


def test_url_shell_variables_and_arbitrary_commands_are_not_association_icons():
    targets = ('https://example.org/file.xlsx', 'shell:Downloads',
               '%file_path%', 'relative.txt', 'C:\\', '')
    for target in targets:
        row = {'item_kind': 'virtual_launch_file', 'icon_key': 'file',
               'launch_actions': [{'launch_action_type': 'Open', 'launch_target': target}]}
        assert icon_lookup(row)[0] == 'default'
    run = {'item_kind': 'virtual_launch_file', 'icon_key': 'file',
           'launch_actions': [{'launch_action_type': 'Run',
                               'launch_target': r'C:\Tmp\test.xlsx'}]}
    assert icon_lookup(run)[0] == 'default'


def test_launcher_uses_type_provider_for_virtual_json_rows_and_caches_by_extension():
    source = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    launcher = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Launcher')
    method = next(n for n in launcher.body if isinstance(n, ast.FunctionDef) and n.name == 'row_icon')
    calls = []

    class FakeIcon:
        def isNull(self):
            return False

    class Provider:
        def icon(self, info):
            calls.append(info)
            return FakeIcon()

    class Stub:
        icon_cache = {}
        file_icons = Provider()

    ns = {'icon_lookup': icon_lookup, 'icon_source_path': icon_source_path, 'QFileInfo': lambda x: x, 'Path': Path,
          'icon': lambda key: ('generic', key)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 'src/app.py', 'exec'), ns)
    rows = _projection()
    for row in rows[:3]:
        assert isinstance(ns['row_icon'](Stub, row), FakeIcon)
    assert calls == ['FRBLaunchTypeSample.xlsx', 'FRBLaunchTypeSample.txt',
                     'FRBLaunchTypeSample.md']
    # Different dropped names of the same type share the cache.
    ns['row_icon'](Stub, {**rows[0], 'launch_actions': [
        {'launch_action_type': 'Open', 'launch_target': r'D:\Other\Other.xlsx'}]})
    assert len(calls) == 3
