"""Regression tests for application-wide Qt filter teardown (no PySide6 needed).

The DOS traceback came from PySide6 calling Launcher-owned event filters in
Qt's atexit shutdown after the Launcher C++ instance had been destroyed.
These AST-level tests execute the real extracted method bodies with doubles.
Windows GUI acceptance is still required for the actual PySide6 runtime.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

APP_SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'app.py'
TREE = ast.parse(APP_SOURCE.read_text(encoding='utf-8'))


def extract_method(class_name, method_name, scope):
    cls = next(node for node in TREE.body
               if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body
                  if isinstance(node, ast.FunctionDef) and node.name == method_name)
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(module, str(APP_SOURCE), 'exec'), scope)
    return scope[method_name]


FILTER_NAMES = (
    '_cascade_outside_click_filter',
    '_history_outside_click_filter',
    '_frame_cursor_reset_filter',
    '_normal_click_activation_filter',
)


class FakeQApplication:
    app = None
    @classmethod
    def instance(cls):
        return cls.app


class FakeApp:
    def __init__(self):
        self.removed = []
    def removeEventFilter(self, obj):
        self.removed.append(obj)


def test_all_four_app_filters_are_detached_once():
    fake_app = FakeApp()
    FakeQApplication.app = fake_app
    launcher = SimpleNamespace(_application_filters_removed=False)
    for name in FILTER_NAMES:
        setattr(launcher, name, object())
    method = extract_method('Launcher', '_remove_application_event_filters', {
        'QApplication': FakeQApplication,
        'qt_object_is_valid': lambda obj: True,
    })
    method(launcher)
    assert launcher._application_filters_removed
    assert fake_app.removed == [getattr(launcher, key) for key in FILTER_NAMES]
    method(launcher)
    assert len(fake_app.removed) == 4, 'Repeated shutdown must not double-remove'


def test_cleanup_skips_already_deleted_qt_filters():
    fake_app = FakeApp()
    FakeQApplication.app = fake_app
    launcher = SimpleNamespace(_application_filters_removed=False)
    for name in FILTER_NAMES:
        setattr(launcher, name, name)
    method = extract_method('Launcher', '_remove_application_event_filters', {
        'QApplication': FakeQApplication,
        'qt_object_is_valid': lambda obj: obj != FILTER_NAMES[1],
    })
    method(launcher)
    assert fake_app.removed == [FILTER_NAMES[0], FILTER_NAMES[2], FILTER_NAMES[3]]


class AlreadyDeleted:
    def __getattribute__(self, name):
        raise RuntimeError('Internal C++ object (Launcher) already deleted')


def test_all_four_filters_ignore_events_after_launcher_cpp_deletion():
    # Include both real failure paths (press) and resize-hover events.
    events = SimpleNamespace(
        Type=SimpleNamespace(MouseMove=1, Leave=2, Enter=3, HoverMove=4,
                             HoverEnter=5, MouseButtonPress=6, KeyPress=7))
    widget_type = type('QWidget', (), {})
    cases = (
        ('FrameEdgeCursorResetFilter', 1),
        ('HistoryOutsideClickFilter', 6),
        ('CascadeOutsideClickFilter', 6),
        ('NormalWindowClickActivationFilter', 6),
    )
    for cls, event_type in cases:
        method = extract_method(cls, 'eventFilter', {
            'QEvent': events,
            'QWidget': widget_type,
            'qt_object_is_valid': lambda obj: False,
        })
        filt = SimpleNamespace(launcher=AlreadyDeleted())
        evt = SimpleNamespace(type=lambda: event_type)
        assert method(filt, widget_type(), evt) is False, cls


def test_all_four_filters_ignore_events_after_explicit_detach():
    events = SimpleNamespace(
        Type=SimpleNamespace(MouseMove=1, Leave=2, Enter=3, HoverMove=4,
                             HoverEnter=5, MouseButtonPress=6, KeyPress=7))
    widget_type = type('QWidget', (), {})
    cases = (
        ('FrameEdgeCursorResetFilter', 1),
        ('HistoryOutsideClickFilter', 6),
        ('CascadeOutsideClickFilter', 7),
        ('NormalWindowClickActivationFilter', 6),
    )
    for cls, event_type in cases:
        method = extract_method(cls, 'eventFilter', {
            'QEvent': events,
            'QWidget': widget_type,
            'qt_object_is_valid': lambda obj: True,
        })
        filt = SimpleNamespace(launcher=SimpleNamespace(_application_filters_removed=True))
        evt = SimpleNamespace(type=lambda: event_type)
        assert method(filt, widget_type(), evt) is False, cls


def test_quit_unregisters_before_application_quit_and_about_to_quit_is_hooked():
    source = APP_SOURCE.read_text(encoding='utf-8')
    cls = next(n for n in TREE.body
               if isinstance(n, ast.ClassDef) and n.name == 'Launcher')
    quit_fn = next(n for n in cls.body
                   if isinstance(n, ast.FunctionDef) and n.name == 'quit')
    unparsed = ast.unparse(quit_fn)
    assert unparsed.index('self._remove_application_event_filters()') < unparsed.index('QApplication.quit()')
    assert 'QApplication.instance().aboutToQuit.connect(self._remove_application_event_filters)' in source
