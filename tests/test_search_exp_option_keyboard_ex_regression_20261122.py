"""Search -> Exp, Options and Keyboard EX regressions; headless contracts.

The source app is a PySide6/Windows UI. These tests execute production
methods through AST extraction without pretending that a desktop was tested.
"""
import ast
import os
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]


def method(module, cls, name, globals_=None):
    source = ROOT / 'src' / module
    parsed = ast.parse(source.read_text(encoding='utf-8'))
    klass = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == name)
    env = dict(globals_ or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(source), 'exec'), env)
    return env[name]


def test_search_exit_refreshes_only_list_and_preserves_exp_model():
    called = []
    data = {'items': []}
    query = ''
    view = NS(
        _workspace_mode='files', _main_search_active=True, _search_data_ref=data,
        isVisible=lambda: True,
        leave_global_search_results=lambda: called.append('leave'),
        refresh_middle=lambda **kwargs: called.append(('refresh_middle', kwargs)),
        refresh=lambda *args: called.append('REBUILD_EXP'),
        setVisible=lambda visible: None,
        hide_favorite_popup=lambda: None,
    )
    sink = NS(setText=lambda value: None, setIcon=lambda value: None,
              setToolTip=lambda value: None, setVisible=lambda value: None)
    app = NS(data=data, expanded_view=view, view_mode='expanded', page_id='system',
             color_theme='light',
             stack=[], selection=None, search=NS(text=lambda: query),
             _read_expanded_options=lambda: {'page_id': 'system'}, footer=sink, list=sink,
             files_root_hidden_mode=False, update_header_tab_width=lambda:None,
             update_files_item_count=lambda: None, _nav_update_buttons=lambda: None,
             mode_button=sink, compact_mode_action=sink)
    run = method('app.py', 'Launcher', 'update_expanded_visibility', {
        'expanded_targets': lambda *_: ([], {}, {}),
        'should_expand': lambda **_: True,
        'view_mode_icon': lambda *_: None,
    })
    run(app)
    assert called == ['leave', ('refresh_middle', {'presentation_only': True})], called


def test_presentation_only_refresh_never_navigates_exp_or_adds_folder_history():
    source = ast.parse((ROOT / 'src' / 'expanded_view.py').read_text('utf-8'))
    cls = next(n for n in source.body if isinstance(n, ast.ClassDef)
               and n.name == 'ExpandedLauncherView')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == 'refresh_middle')
    assert fn.args.kwonlyargs[0].arg == 'presentation_only'
    # The shared function contains both the virtual and physical branches;
    # both must guard history, and the physical branch must guard Exp sync.
    guards = [n for n in ast.walk(fn) if isinstance(n, ast.If)
              and isinstance(n.test, ast.UnaryOp)
              and isinstance(n.test.op, ast.Not)
              and isinstance(n.test.operand, ast.Name)
              and n.test.operand.id == 'presentation_only']
    assert len(guards) >= 2
    assert 'not presentation_only and callable(changed)' in (ROOT/'src/expanded_view.py').read_text('utf-8')


def test_exp_navigation_clears_search_once_without_recording_old_folder():
    events = []
    view = NS(_main_search_active=True, _suspend_folder_location_record=False,
              _remember_main_search_cursor=lambda: events.append('remember'))
    def clear():
        assert view._suspend_folder_location_record
        events.append('clear')
    app = NS(expanded_view=view,
             _live_search_timer=NS(stop=lambda: events.append('stop')),
             search=NS(clear=clear))
    go = method('app.py', 'Launcher', '_leave_search_before_exp_navigation')
    assert go(app)
    assert events == ['remember', 'stop', 'clear']
    assert not view._suspend_folder_location_record
    view._main_search_active = False
    assert not go(app)
    assert events == ['remember', 'stop', 'clear']


def test_keyboard_ex_search_current_folder_has_canonical_anchor_even_if_search_gone(tmp_path):
    calls = []
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              _main_search_active=False,
              go_to_directory=lambda target, **kwargs:
                  calls.append(('go', target, kwargs)) or True)
    app = NS(expanded_view=view,
             _current_remote_files_exp=lambda: None,
             _leave_search_before_exp_navigation=lambda: calls.append('prepare'))
    source = NS(data=lambda role: {'slash_transient': True, 'slash_search_result': True})
    run = method('app.py', 'Launcher', 'navigate_files_exp_folder', {
        'Path': Path, 'Qt': NS(ItemDataRole=NS(UserRole=100))})
    assert run(app, str(tmp_path), origin_item=source)
    assert calls[0] == 'prepare'
    assert calls[1][0:2] == ('go', str(tmp_path))
    assert calls[1][2]['absolute_location'] is True
    assert 'direct_anchor' not in calls[1][2]
    assert calls[1][2]['preserve_remote_popup'] is True


def test_keyboard_ex_self_row_uses_existing_folder_navigation(tmp_path):
    calls = []
    run = method('slash_exp_navigation.py', 'SlashExpMenu', '_commit_terminal', {
        '_DATA_ROLE': 101, 'os': os,
    })
    app = NS(navigate_files_exp_folder=lambda path, **kwargs:
             calls.append(('navigate', path, kwargs)) or True)
    menu = NS(launcher=app, panel='Exp', source_item='search-result-source',
              _commit_folder_and_focus=lambda committed, **kw: committed)
    item = NS(data=lambda role: {'current_folder': True, 'path': str(tmp_path)})
    assert run(menu, item)
    assert calls == [('navigate', str(tmp_path),
                      {'origin_panel': 'Exp', 'origin_item': 'search-result-source'})]
    source = (ROOT/'src/slash_exp_navigation.py').read_text('utf-8')
    assert "'slash_search_result': True" in source
    assert '# The Keyboard EX self-row is also a mouse command.' in source


def test_options_always_target_third_column_even_when_studio_embed_switch_is_off():
    calls = []
    menu = NS(findChildren=lambda kind: [], close=lambda: calls.append('close'),
              hide=lambda: calls.append('hide'),
              setActiveAction=lambda action: None)
    view = NS(isVisible=lambda:True,
              show_files_view=lambda: calls.append('files'),
              show_option_settings_preview=lambda *args: calls.append('third') or True)
    app = NS(theme_menu=menu, expanded_view=view, _remote_context_wheel=None,
             _option_settings_pending=True)
    run = method('app.py', 'Launcher', '_show_option_settings_after_menu_close', {
        'QMenu': object, 'LAUNCH_HOME': 'root', 'STATE':'state',
        'os': NS(name='nt'),
    })
    app.expander=lambda: NS(values={'studio_root': 'studio'})
    run(app)
    assert calls == ['close', 'hide', 'files', 'third']
    assert not app._option_settings_pending

    # Busy/blocked Studio: never create a competing modal dialog.
    calls.clear()
    view.show_option_settings_preview=lambda *args: calls.append('busy') or False
    app.info_notice=lambda text: calls.append('notice')
    run(app)
    assert calls == ['close', 'hide', 'files', 'busy', 'notice']


def test_keyboard_ex_virtual_and_exp_pc_use_same_search_exit_boundary():
    calls = []
    view = NS(isVisible=lambda: True, _workspace_mode='files',
              show_virtual_launch_directory=lambda node:
                  calls.append(('virtual', node)) or True)
    app = NS(expanded_view=view,
             _leave_search_before_exp_navigation=lambda: calls.append('leave'),
             set_files_operating_target=lambda target: calls.append(('target', target)),
             _files_operating_target='files_exp')
    node = {'source': 'launch_json', 'kind': 'folder', 'node_id': 'work'}
    run_virtual = method('app.py', 'Launcher', 'navigate_virtual_launch_folder')
    assert run_virtual(app, node)
    assert calls == ['leave', ('virtual', node)]

    calls.clear()
    pc_item = object()
    tree = NS(topLevelItemCount=lambda: 1, topLevelItem=lambda index: pc_item,
              setCurrentItem=lambda item: calls.append(('current', item)))
    view.left = NS(tree=tree)
    view.row_data = lambda item: {'_system_drives_root':True}
    view.choose_files = lambda item, column: calls.append(('choose', item, column))
    run_pc = method('app.py', 'Launcher', 'navigate_files_exp_pc')
    assert run_pc(app)
    assert calls[:3] == ['leave', ('current', pc_item), ('choose', pc_item, 0)]
