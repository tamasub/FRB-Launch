"""Search is a Location, not a made-up directory (Qt-free contract tests)."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from directory_navigation_history import DirectoryNavigationHistory
from expanded_view_model import normalize_options, should_expand
from location_model import Location, search_breadcrumb, search_list_rows, search_location


def extract_view_method(name, namespace=None):
    tree = ast.parse((ROOT / 'src/expanded_view.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'ExpandedLauncherView')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == name)
    scope = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 '<expanded-view-method>', 'exec'), scope)
    return scope[name]


def test_location_search_is_not_virtual_or_physical_path():
    result = search_location('  佐藤  ')
    assert result == Location('search', '佐藤', '🔍 検索結果：佐藤')
    assert search_breadcrumb(' 佐藤 ') == [('🔍 検索結果：佐藤', ('search', '佐藤'))]
    with pytest.raises(ValueError):
        search_location('  ')
    with pytest.raises(ValueError):
        Location('fictional', 'x', 'x')


def test_search_projection_keeps_authored_and_physical_identity_and_actions():
    configured = {'title': 'Windows', 'item_id': 'win', 'page_id': 'work',
                  'item_kind': 'category', 'launch_actions': [{'launch_action_type': 'Open',
                                                                'launch_target': 'demo'}]}
    physical = {'title': 'memo.md', 'item_id': '__file_index_example',
                'item_kind': 'command', '_indexed_file': r'C:\Notes\memo.md'}
    contact = {'title': '佐藤 次郎', 'item_kind': 'choice', 'choice_id': 'choice2',
               '_search_selection_owner': 'recipients', 'value': 'hello@example.invalid'}
    original = [(configured, 'My Work'), (physical, 'ファイル索引'),
                (contact, 'My Work / メール')]
    projected = search_list_rows(original)
    assert [row['_search_item_type'] for row in projected] == [
        'フォルダー', 'ファイル', '選択候補']
    assert projected[0]['launch_actions'] == configured['launch_actions']
    assert projected[0]['item_id'] == 'win'
    assert 'My Work' in projected[0]['_search_description']
    assert projected[1]['_indexed_file'] == r'C:\Notes\memo.md'
    assert projected[2]['choice_id'] == 'choice2'
    assert projected[2]['_search_selection_owner'] == 'recipients'
    assert all(row['_main_search_result'] for row in projected)
    assert all('_main_search_result' not in old for old, _ in original)


def test_search_is_expanded_destination_but_selection_flow_uses_legacy_picker():
    base = dict(view_mode='expanded', page_id='system', query='佐藤', stack=[],
                selection=None, options=normalize_options(None), available=True)
    assert should_expand(**base)
    assert not should_expand(**{**base, 'selection': {'item_id': 'recipients'}})
    assert not should_expand(**{**base, 'page_id': 'work'})
    assert not should_expand(**{**base, 'stack': [{'item_id': 'folder'}]})


def test_history_contains_search_between_distinct_folders_and_can_return():
    history = DirectoryNavigationHistory()
    virtual = [{'item_id': 'my_work'}]
    assert history.record(None, virtual)
    assert history.record_search('佐藤', current_item_id='c1', scroll=40)
    # Updating selection/scroll must not make another navigation stop.
    assert not history.record_search('佐藤', current_item_id='c2', scroll=80)
    assert len(history.entries) == 2
    assert history.current['kind'] == 'search'
    assert history.current['current_item_id'] == 'c2'
    assert history.current['scroll'] == 80
    assert history.record(r'C:\Users\Test', [{'item_id': 'real'}])
    assert history.back()['query'] == '佐藤'
    assert history.back()['key'][0] == 'virtual'
    assert history.forward()['kind'] == 'search'
    assert history.forward()['path'] == r'C:\Users\Test'
    assert not history.can_forward


def test_search_history_branches_after_back_and_never_treats_query_as_path():
    history = DirectoryNavigationHistory()
    history.record(r'C:\Root', [{'item_id': 'root'}])
    history.record_search('alpha')
    history.record(r'D:\Target', [{'item_id': 'target'}])
    history.back()
    assert not history.record_search('beta')
    # The active Search location changes query without creating an extra stop.
    assert [entry['key'][0] for entry in history.entries] == [
        'filesystem', 'search']
    assert history.current['query'] == 'beta'
    assert not history.can_forward
    assert 'path' not in history.entries[-1]


def test_open_indexed_search_folder_keeps_search_until_destination_valid(tmp_path):
    visited = []
    search = NS(clear=lambda: visited.append('clear'))
    owner = NS(launcher=NS(search=search),
               _remember_main_search_cursor=lambda: visited.append('remember'),
               go_to_directory=lambda path, **kw: visited.append(('open', path, kw)) or True)
    fn = extract_view_method('open_main_search_folder', {'os': __import__('os')})
    bad = {'item_kind': 'directory', '_main_search_result': True,
           '_file': str(tmp_path / 'missing')}
    assert not fn(owner, bad)
    assert not visited
    valid = {'item_kind': 'directory', '_main_search_result': True,
             '_file': str(tmp_path)}
    assert fn(owner, valid)
    assert visited == ['remember', 'clear',
                       ('open', str(tmp_path), {'direct_anchor': True})]
    assert owner._suspend_folder_location_record is False


def test_open_json_category_search_result_resolves_canonical_node_once():
    calls = []
    node = {'kind': 'category', 'source': 'launch_json', 'node_id': 'item:work:mail'}
    fn = extract_view_method('open_main_search_folder', {
        'os': __import__('os'),
        'virtual_lookup_node': lambda pages, authored, pg, item, runtime:
            calls.append(('resolve', pg, item)) or node,
    })
    owner = NS(launcher=NS(pages=[], authored_items=[], data={'items': []},
                           search=NS(clear=lambda: calls.append('clear'))),
               _remember_main_search_cursor=lambda: calls.append('remember'),
               show_virtual_launch_directory=lambda item:
                   calls.append(('navigate', item)) or True)
    row = {'_main_search_result': True, 'item_kind': 'category',
           'page_id': 'work', 'item_id': 'mail'}
    assert fn(owner, row)
    assert calls == [('resolve', 'work', 'mail'), 'remember', 'clear', ('navigate', node)]
    assert owner._suspend_folder_location_record is False


def test_wiring_same_list_context_and_selection_exception_unchanged():
    app = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    view = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    slash = (ROOT / 'src/slash_exp_navigation.py').read_text(encoding='utf-8')
    ast.parse(app); ast.parse(view); ast.parse(slash)
    assert 'self.expanded_view.show_global_search_results(' in app
    assert 'self.expanded_view.leave_global_search_results()' in app
    assert 'self.middle.fill(rows, self.launcher.row_icon)' in view
    assert 'search_breadcrumb(query)' in view
    assert "row.get('_search_selection_owner')" in view
    assert 'self.launcher.activate(row)' in view
    assert 'slash_source_from_search_result' in slash
    assert 'return self._restore_directory_history(self.directory_history.back())' in view


def test_history_restores_search_query_without_inventing_folder():
    calls = []
    editor = NS(setText=lambda value: calls.append(('query', value)))
    launcher = NS(search=editor, render=lambda: calls.append('render'),
                  _nav_update_buttons=lambda: calls.append('buttons'))
    view = NS(launcher=launcher, _restoring_directory_history=False,
              _restore_main_search_cursor=lambda entry: calls.append('cursor'),
              focus_panel=lambda pane: calls.append('focus'), middle=object())
    restore = extract_view_method('_restore_directory_history')
    entry = {'kind': 'search', 'query': '鈴木', 'current_item_id': 'choice1',
             'scroll': 123}
    assert restore(view, entry)
    assert calls == [('query', '鈴木'), 'render', 'cursor', 'focus', 'buttons']
    assert view._restoring_directory_history is False
    assert not hasattr(view, 'path')


def test_search_location_has_no_cascade_parent_and_authored_context_is_retained():
    view = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    assert "if target[0] == 'search':" in view
    assert "if getattr(self, '_main_search_active', False):\n            return self.history_back()" in view
    assert 'self.launcher.show_virtual_launch_context(' in view
    assert 'self.launcher.show_launch_context_menu(' in view
    assert "row.get('item_kind') == 'selection'" in view


def test_typing_many_search_characters_is_one_navigation_stop():
    history = DirectoryNavigationHistory()
    history.record(r'C:\Work', [{'item_id': 'folder'}])
    assert history.record_search('佐')
    assert not history.record_search('佐藤')
    assert not history.record_search('佐藤 次')
    assert not history.record_search('佐藤 次郎', current_item_id='choice2')
    assert len(history.entries) == 2
    assert history.current['query'] == '佐藤 次郎'
    assert history.current['current_item_id'] == 'choice2'
    assert history.back()['path'] == r'C:\Work'


def test_forward_history_survives_search_cursor_updates_after_back():
    history = DirectoryNavigationHistory()
    history.record(r'C:\Source', [{'item_id': 'source'}])
    history.record_search('佐藤')
    history.record(r'C:\Target', [{'item_id': 'target'}])
    assert history.back()['query'] == '佐藤'
    assert history.can_forward
    assert not history.record_search('佐藤', current_item_id='contact', scroll=31)
    assert history.can_forward, 'Restoring a search cursor must preserve forward'
    assert history.forward()['path'] == r'C:\Target'
