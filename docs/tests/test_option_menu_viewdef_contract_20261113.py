"""Option Settings regression: Tool QMenu dismissal, Launch-owned ViewDef."""
from __future__ import annotations
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'src/app.py').read_text(encoding='utf-8')


def method(name,scope=None):
    tree=ast.parse(APP)
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Launcher')
    fn=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
    namespace=scope or {}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'app.py','exec'),namespace)
    return namespace[name]


class Menu:
    def __init__(self):
        self.visible=True
        self.close=Mock(side_effect=self._close)
        self.hide=Mock(side_effect=self._close)
        self.setActiveAction=Mock()
        self.findChildren=lambda _:[]
    def _close(self):self.visible=False


class Timer:
    scheduled=[]
    @classmethod
    def singleShot(cls,delay,callback):
        assert delay==0
        cls.scheduled.append(callback)


def test_option_menu_is_closed_after_action_event_and_before_dialog():
    menu=Menu(); window=SimpleNamespace(isVisible=lambda:True,raise_=Mock(),activateWindow=Mock())
    obj=SimpleNamespace(theme_menu=menu,_option_settings_window=window,_option_settings_pending=False,
                        _remote_context_wheel=None,error=Mock())
    obj._show_option_settings_after_menu_close=lambda:method('_show_option_settings_after_menu_close',{'QMenu':object})(obj)
    Timer.scheduled=[]
    method('open_option_settings',{'QMenu':object,'QTimer':Timer})(obj)
    assert menu.close.call_count==1
    assert not menu.visible
    assert len(Timer.scheduled)==1
    # QAction mouse release has not fully unwound when called synchronously.
    # The delayed second close must win even if the Tool menu was re-shown.
    menu.visible=True
    Timer.scheduled.pop()()
    assert menu.close.call_count==2
    assert menu.hide.call_count==2
    assert not menu.visible
    assert window.raise_.call_count==1
    menu.setActiveAction.assert_called_once_with(None)
    assert not obj._option_settings_pending


def test_launch_owns_viewdefs_and_only_one_registry():
    base=ROOT/'defs/launch/options'
    registry=json.loads((base/'options_registry.json').read_text(encoding='utf-8'))
    assert [x['id'] for x in registry['options']]==['webview','file_index']
    for x in registry['options']:
        assert (ROOT/x['viewDef']).is_file()
    file_index=json.loads((base/'file_index_options_view_def_v0_1.json').read_text(encoding='utf-8'))
    fields=file_index['views'][0]['sections'][0]['fields']
    mode=next(f for f in fields if f['field']=='index_mode')
    assert [o['value'] for o in mode['options']]==['registered','configured','off']
    assert all(any(ord(c)>127 for c in o['label']) for o in mode['options'])
    folders=next(f for f in fields if f['field']=='index_folders')
    assert folders['visibleWhen']=={'field':'index_mode','equals':'configured'}
    help_field=next(f for f in fields if f['field']=='_index_mode_help')
    assert help_field['type']=='textarea' and help_field['readonly']
    assert help_field['edit']['readonly'] is True
    assert 'registered' in help_field['defaultValue']
    webview=json.loads((base/'webview_settings_view_def_v0_1.json').read_text(encoding='utf-8'))
    assert [x['field'] for x in webview['views'][0]['sections'][0]['fields']]==['remember_login','new_tab_url']
