"""2026-11-17: Files List local search Esc must match QLineEdit's ×.

Run the production event adapter without requiring Windows/PySide6.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'src' / 'expanded_view.py').read_text(encoding='utf-8')


def production_method(name):
    tree = ast.parse(SOURCE)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'ExpandedLauncherView')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == name)
    namespace = {
        'Qt': NS(Key=NS(Key_Escape=27, Key_Return=13),
                 KeyboardModifier=NS(NoModifier=0, ControlModifier=1)),
        'QEvent': NS(Type=NS(KeyPress=6, MouseButtonPress=2)),
    }
    exec(compile(ast.get_source_segment(SOURCE, func), 'expanded_view.py', 'exec'),
         namespace)
    return namespace[name]


class Editor:
    def __init__(self, value='.md', focus=True):
        self.value = value
        self.focus = focus
        self.clear_count = 0
        self.text_changed = []

    def hasFocus(self):
        return self.focus

    def text(self):
        return self.value

    def clear(self):
        self.clear_count += 1
        self.value = ''
        self.text_changed.append('')  # QLineEdit textChanged signal behavior


class Event:
    def __init__(self, key=27, event_type=6, modifiers=0):
        self._key, self._type, self._mods = key, event_type, modifiers
        self.accepted = False

    def key(self): return self._key
    def type(self): return self._type
    def modifiers(self): return self._mods
    def accept(self): self.accepted = True


def test_esc_clears_focused_files_search_via_existing_clear_operation():
    editor = Editor('.md')
    view = NS(middle_search=editor, _workspace_mode='files',
              isVisible=lambda: True)
    event = Event()
    assert production_method('clear_middle_search_on_escape')(view, editor, event) is True
    assert editor.value == ''
    assert editor.clear_count == 1
    assert editor.text_changed == ['']
    assert event.accepted


def test_escape_does_not_clear_other_fields_or_when_focus_is_elsewhere():
    method = production_method('clear_middle_search_on_escape')
    editor = Editor('.md')
    view = NS(middle_search=editor, _workspace_mode='files',
              isVisible=lambda: True)
    event = Event()
    assert method(view, object(), event) is False
    assert editor.value == '.md' and not event.accepted
    editor.focus = False
    assert method(view, editor, event) is False
    assert editor.value == '.md'


def test_empty_filter_and_browser_mode_preserve_existing_escape_behavior():
    method = production_method('clear_middle_search_on_escape')
    editor = Editor('')
    view = NS(middle_search=editor, _workspace_mode='files',
              isVisible=lambda: True)
    assert method(view, editor, Event()) is False
    assert editor.clear_count == 0
    editor.value = '.md'
    view._workspace_mode = 'browser'
    assert method(view, editor, Event()) is False
    view._workspace_mode = 'files'
    view.isVisible = lambda: False
    assert method(view, editor, Event()) is False


def test_other_keys_modifiers_and_event_types_remain_unaffected():
    method = production_method('clear_middle_search_on_escape')
    editor = Editor('.md')
    view = NS(middle_search=editor, _workspace_mode='files',
              isVisible=lambda: True)
    for event in (Event(key=13), Event(modifiers=1), Event(event_type=2)):
        assert method(view, editor, event) is False
        assert not event.accepted
    assert editor.value == '.md' and editor.clear_count == 0


def test_event_filter_checks_local_escape_before_history_and_global_navigation():
    cls = next(n for n in ast.parse(SOURCE).body if isinstance(n, ast.ClassDef)
               and n.name == 'ExpandedLauncherView')
    event_filter = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'eventFilter')
    body = ast.get_source_segment(SOURCE, event_filter)
    assert body.index('self.clear_middle_search_on_escape(obj, event)') < body.index(
        'self.handle_middle_search_history_key(obj, event)')
    assert 'self.middle_search.textChanged.connect(self.apply_middle_filter)' in SOURCE
    assert "self.middle_search.setClearButtonEnabled(True)" in SOURCE
