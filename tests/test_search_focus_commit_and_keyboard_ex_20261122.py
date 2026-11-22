"""Search Focus/Keyboard EX regression contracts (headless)."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def method(src, cls, name, env=None):
    parsed = ast.parse((ROOT / 'src' / src).read_text(encoding='utf-8'))
    target = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in target.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(env or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(ROOT / 'src' / src), 'exec'), scope)
    return scope[name]


def test_enter_commits_search_to_list_but_live_typing_does_not():
    calls = []
    search = object()
    popup = NS(isVisible=lambda: False)
    history = NS(viewport=lambda: object())
    event = NS(type=lambda: 'press', key=lambda: 13, modifiers=lambda: 0,
               text=lambda: '', accept=lambda: calls.append('accept'))
    qt = NS(Key=NS(Key_F3=114, Key_Slash=47, Key_Down=40, Key_Return=13,
                   Key_Enter=16777221),
            KeyboardModifier=NS(NoModifier=0, ShiftModifier=1))
    env = {'QEvent': NS(Type=NS(KeyPress='press', MouseButtonPress='mouse')),
           'Qt': qt}
    owner = NS(search=search, list=object(), tabs=object(),
               history_choices=history, history_filter=object(), history_popup=popup,
               composing=False,
               flush_live_search=lambda: calls.append('flush'),
               focus_settled_global_search_results=lambda: calls.append('focus-list') or True,
               record_session_search=lambda: calls.append('session-history'),
               _session_edit_draft='draft')
    fn = method('app.py', 'Launcher', 'handle_history_event', env)
    assert fn(owner, search, event)
    assert calls == ['flush', 'focus-list', 'session-history', 'accept']
    assert owner._session_edit_draft is None
    # The live render contains no focus handoff.
    source = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    assert 'self.render()\n\n    def focus_settled_global_search_results' in source


def test_leave_search_list_only_on_actual_focus_exit():
    calls = []
    list_tree, local_search, breadcrumb = object(), object(), object()
    class Widget:
        def __init__(self, *children): self.children = children
        def isAncestorOf(self, widget): return widget in self.children
        def isVisible(self): return True
    tree = Widget(list_tree)
    local = Widget(local_search)
    menu = Widget()
    is_open = {'value': False}
    menu.isVisible = lambda: is_open['value']
    view = NS(_main_search_active=True, middle=NS(tree=tree),
              middle_search=local, middle_search_history_button=None,
              middle_search_history_menu=None)
    owner = NS(expanded_view=view, _search_list_focus_session=False,
               _search_list_context_popup=menu,
               _slash_exp_navigation_menu=None,
               clear_global_search_from_list=lambda **kw: calls.append(('clear',kw)) or True)
    self_methods = {
        'context': method('app.py','Launcher','_search_list_focus_context'),
        'popup': method('app.py','Launcher','_search_list_popup_open'),
        'end': method('app.py','Launcher','_finish_search_list_focus_exit'),
    }
    owner._search_list_focus_context = lambda w: self_methods['context'](owner,w)
    owner._search_list_popup_open = lambda: self_methods['popup'](owner)
    current = {'widget': list_tree}
    self_methods['end'].__globals__['QApplication'] = NS(focusWidget=lambda:current['widget'])
    scheduled = []
    track = method('app.py','Launcher','_track_search_list_focus',{
        'QTimer': NS(singleShot=lambda delay, callback: scheduled.append(callback))})
    owner._finish_search_list_focus_exit = lambda: self_methods['end'](owner)
    # It starts only after List actually holds keyboard focus.
    track(owner,breadcrumb)
    assert not scheduled and not calls
    track(owner,list_tree)
    assert owner._search_list_focus_session
    track(owner,local_search)
    assert not scheduled  # folder-search stays within List ownership
    track(owner,breadcrumb)
    assert len(scheduled)==1
    current['widget']=local_search
    assert not scheduled.pop(0)()  # async handoff returned to List
    track(owner,breadcrumb)
    current['widget']=breadcrumb
    is_open['value']=True
    assert not scheduled.pop(0)()  # visible List context menu still owns List
    assert not calls
    is_open['value']=False
    assert owner._finish_search_list_focus_exit()
    assert calls == [('clear', {'preserve_focus':True})]
    assert not owner._search_list_focus_session


def test_search_backspace_focus_behavior_stays_distinct():
    events = []
    view = NS(_main_search_active=True, _workspace_mode='files',
              isVisible=lambda:True,
              _focus_files_keyboard_area=lambda area:events.append(('focus',area)))
    owner = NS(expanded_view=view, search=NS(text=lambda:'abc',clear=lambda:events.append('clear')),
               hide_history_popup=lambda:events.append('hide'),
               _live_search_timer=NS(stop=lambda:events.append('stop')),
               _search_list_focus_session=True)
    fn = method('app.py','Launcher','clear_global_search_from_list')
    assert fn(owner,preserve_focus=True)
    assert events == ['stop','hide','clear']
    assert owner._search_list_focus_session is False
    owner._search_list_focus_session=True
    assert fn(owner)
    assert events[-1] == ('focus','list')


def test_slash_from_search_file_uses_real_parent_and_json_leaf_uses_group(tmp_path):
    from launch_virtual_tree import virtual_lookup_node
    class FakeStandardItem:
        def __init__(self, icon, name):
            self.name, self.saved = name, {}
        def setData(self, value, role): self.saved[role] = value
    def row_view(row):
        return NS(middle=NS(tree=NS(currentItem=lambda: row)),
                  row_data=lambda item: item)
    # slash_source_from_search_result is a plain function, not a class method.
    parsed = ast.parse((ROOT/'src'/'slash_exp_navigation.py').read_text('utf-8'))
    fn = next(node for node in parsed.body if isinstance(node, ast.FunctionDef)
              and node.name == 'slash_source_from_search_result')
    globals_ = {'os':__import__('os'), 'QStandardItem':FakeStandardItem,
                'QIcon':lambda:None, '_DATA_ROLE':10, '_LOADED_ROLE':11}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),
                 '<slash-ex-source>','exec'),globals_)
    choose=globals_['slash_source_from_search_result']
    file = tmp_path/'memo.md'
    file.write_text('example',encoding='utf-8')
    launcher = NS(pages=[],authored_items=[],data={})
    physical = {'_main_search_result':True, 'item_kind':'command',
                '_indexed_file':str(file), 'title':'memo.md'}
    item = choose(launcher,row_view(physical),None)
    assert item.saved[10]['path'] == str(tmp_path)
    assert item.saved[11] is True  # detached search item must never expand the Exp model
    pages = [{'page_id':'work','title':'My Work'}]
    rows = [
        {'page_id':'work','item_id':'group','title':'Mail', 'item_kind':'category'},
        {'page_id':'work','item_id':'item', 'parent_item_id':'group',
         'title':'Open URL','item_kind':'command'},
    ]
    launcher = NS(pages=pages,authored_items=rows,data={})
    leaf = {'_main_search_result':True, 'item_kind':'command',
            'page_id':'work','item_id':'item'}
    source=choose(launcher,row_view(leaf),None)
    assert source.saved[10]['virtual']['item_id'] == 'group'
    assert source.saved[11] is True
    choice = dict(leaf,_search_selection_owner='mail')
    assert choose(launcher,row_view(choice),None) is None
    assert choose(launcher,row_view({'_main_search_result':True,'item_kind':'command',
                                    '_indexed_file':str(file)+'missing'}),None) is None


def test_menu_key_and_slash_both_route_search_to_keyboard_ex():
    events=[]
    owner = NS(_slash_exp_navigation_menu=None,
               show_slash_exp_navigation_menu=lambda:events.append('keyboard-ex') or True)
    fn=method('app.py','Launcher','toggle_slash_exp_shortcut',{
        'QApplication':NS(focusWidget=lambda:object()),
        'QLineEdit':type('Line',(),{}),
        'QPlainTextEdit':type('Plain',(),{}),
        'QComboBox':type('Combo',(),{}),
    })
    assert fn(owner)
    assert events == ['keyboard-ex']
    app = (ROOT/'src'/'app.py').read_text('utf-8')
    # Search branch must declare its absent folder breadcrumb: no UnboundLocalError.
    assert 'breadcrumb_source = None  # Search Locations have no folder breadcrumb.' in app
    assert "source_item = slash_source_from_search_result(self, view, panel)" in app
