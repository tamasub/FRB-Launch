"""Commander floating choices regression checks (no GUI needed in CI).

Runtime GUI acceptance is Windows/PySide6 only; these tests deliberately
validate the UI ownership and control-flow contract without mocking Qt.
"""
import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'commander' / 'window.py'


def _method(name):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'CommanderWindow')
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == name)


def _calls(method):
    return [node for node in ast.walk(method) if isinstance(node, ast.Call)]


def _calls_attr(method, attr):
    return [node for node in _calls(method)
            if isinstance(node.func, ast.Attribute) and node.func.attr == attr]


def test_editor_and_list_share_external_popup_not_main_layout():
    init = _method('__init__')
    source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), init)
    assert 'self.search = QLineEdit(self.candidate_popup)' in source
    assert 'candidate_layout.addWidget(self.search)' in source
    assert 'root.addWidget(self.search)' not in source
    assert 'self.listbox = QListWidget(self.candidate_popup)' in source
    assert 'root.addWidget(self.candidate_popup)' not in source
    assert 'self.chooser' not in source


def test_choices_are_activatable_native_tool_window_for_ime():
    init_source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('__init__'))
    assert 'Qt.WindowType.Tool' in init_source
    assert 'Qt.WindowType.FramelessWindowHint' in init_source
    assert 'Qt.WindowType.WindowDoesNotAcceptFocus' not in init_source
    assert 'Qt.WidgetAttribute.WA_ShowWithoutActivating' not in init_source
    focus = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('_focus_popup_search'))
    assert 'self.candidate_popup.activateWindow()' in focus
    assert 'self.search.setFocus(' in focus
    assert 'self.candidate_popup = QFrame(self, flags)' in init_source


def test_showing_choices_never_resizes_commander_or_moves_editor():
    for method in ('open_selection', '_filter_candidates', '_show_candidate_popup'):
        node = _method(method)
        for call in _calls_attr(node, 'resize') + _calls_attr(node, 'move'):
            assert isinstance(call.func.value, ast.Attribute)
            assert call.func.value.attr == 'candidate_popup'
    place_source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'),
                                          _method('_place_candidate_popup'))
    assert 'crumb = self._active_crumb()' in place_source
    assert 'crumb.mapToGlobal' in place_source
    assert not _calls_attr(_method('_filter_candidates'), '_show_candidate_popup')
    assert 'screen.availableGeometry()' in place_source


def test_choice_close_and_commander_hide_close_floating_window():
    for method in ('hideEvent', 'closeEvent'):
        source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method(method))
        assert 'self.close_candidates(restore_focus=False)' in source
    source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'),
                                    _method('close_candidates'))
    assert 'self.candidate_popup.hide()' in source
    assert 'removeEventFilter(self)' in source
    assert 'self.focus_breadcrumb()' in source


def test_keyboard_ex_picker_remains_the_original_separate_flow():
    source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'),
                                    _method('open_file_picker'))
    assert 'popup_exp_navigator' in source
    assert 'on_file_selected=' in source


def test_event_filters_installed_after_all_dependencies():
    source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('__init__'))
    first_install = source.index('.installEventFilter(self)')
    for dependency in ('self.search =', 'self.listbox =', 'self.candidate_popup =', 'self.breadcrumb_layout =', 'self.refresh_breadcrumbs()'):
        assert source.index(dependency) < first_install
    assert source.rindex('.installEventFilter(self)') < source.index('self._event_filter_ready = True')


def test_event_filter_safe_during_partial_construction():
    # Execute the actual method with a minimal base; an early Qt callback must
    # not read search/listbox/popup or even inspect the event before readiness.
    class Base:
        def eventFilter(self, obj, event):
            return False
    method = _method('eventFilter')
    cls = ast.ClassDef(name='Probe', bases=[ast.Name(id='Base', ctx=ast.Load())], keywords=[], body=[method], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = {'Base': Base}
    exec(compile(module, str(SOURCE), 'exec'), namespace)
    probe = namespace['Probe']()
    assert probe.eventFilter(object(), object()) is False
    probe._event_filter_ready = False
    assert probe.eventFilter(object(), object()) is False


def test_mouse_crumb_opens_same_selection_as_keyboard():
    source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('refresh_breadcrumbs'))
    assert 'QPushButton(text, self.breadcrumb_frame)' in source
    assert 'label.clicked.connect' in source
    assert 'self._click_breadcrumb(i)' in source
    click = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('_click_breadcrumb'))
    assert 'self.focus_index = index' in click
    assert 'self.open_selection()' in click
    picker = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('open_file_picker'))
    assert 'crumb = self._active_crumb()' in picker


def test_free_text_has_mouse_confirmation_inside_popup():
    source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('__init__'))
    assert "QPushButton('確定  Enter', self.candidate_popup)" in source
    assert 'self.text_confirm.clicked.connect(self._accept_choice)' in source
    selection = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), _method('open_selection'))
    assert 'self.text_confirm.setVisible(not is_choice)' in selection
    assert 'self.listbox.setVisible(is_choice)' in selection
