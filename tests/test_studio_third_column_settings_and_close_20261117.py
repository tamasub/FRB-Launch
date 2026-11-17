"""Third-column Studio/Option routing regression checks.

Windows HWND/WebView2 actual interaction needs an on-device acceptance pass;
these checks cover the portable routing, keyboard/menu contract, and pane sizes.
"""
import ast
from pathlib import Path

from preview_splitter_layout import preview_sizes
from studio_preview_route import studio_start_command

SRC = Path(__file__).resolve().parents[1] / 'src'


def method_source(file, cls, name):
    tree = ast.parse((SRC / file).read_text(encoding='utf-8'))
    owner = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == cls)
    node = next(x for x in owner.body if isinstance(x, ast.FunctionDef) and x.name == name)
    return ast.get_source_segment((SRC / file).read_text(encoding='utf-8'), node)


def test_authored_launch_menu_flags_pass_unchanged_to_native_shell():
    target = (
        'C:/Launch/UserConfig/frb_launch_data.json',
        'C:/Studio/NativeShell/_publish/FRBStudio.NativeShell.exe',
        'C:/Studio',
        ('--launch-home=C:/Launch', '--launch-view-def=C:/Launch/defs/menu.json',
         '--launch-page-id=2'),
    )
    cmd, cwd = studio_start_command(target)
    assert cmd[1] == '--open-json=' + target[0]
    assert cmd[2:] == list(target[3])
    assert cwd == 'C:/Studio'


def test_browser_third_column_correct_with_studio_created_first():
    assert preview_sizes([260, 1000], 4, 3, 460, 230) == [260, 540, 0, 460]


def test_studio_third_column_correct_with_browser_created_first():
    assert preview_sizes([260, 1000], 4, 3, 630, 170) == [260, 370, 0, 630]
    assert preview_sizes([260, 1000], 4, 2, 630, 170) == [260, 370, 630, 0]


def test_no_incorrect_two_column_geometry():
    import pytest
    with pytest.raises(ValueError):
        preview_sizes([200, 500], 4, 4, 300, 170)


def test_close_hides_but_never_undocks_or_exits_studio():
    src = method_source('expanded_view.py', 'ExpandedLauncherView', 'close_studio_preview')
    assert 'self._hide_studio_preview_only()' in src
    assert 'panel.undock()' not in src
    assert '.terminate(' not in src and '.kill(' not in src
    exit_src = method_source('expanded_view.py', 'ExpandedLauncherView', 'release_studio_preview')
    assert 'self.studio_preview.undock()' in exit_src


def test_menu_and_options_open_third_column_before_old_popup_fallback():
    launch = method_source('app.py', 'Launcher', 'launch_configuration_studio')
    assert 'view.show_studio_preview(target)' in launch
    assert launch.index('view.show_studio_preview(target)') < launch.index('self.execute({')
    options = method_source('app.py', 'Launcher', '_show_option_settings_after_menu_close')
    assert 'view.show_option_settings_preview(' in options
    assert options.index('view.show_option_settings_preview(') < options.index('dialog.show()')


def test_native_options_same_editor_not_second_save_path():
    panel = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'from option_settings_window import OptionSettingsWindow' in panel
    assert 'options.setWindowFlags(Qt.WindowType.Widget)' in panel
    assert 'self.content_stack.setCurrentWidget(self._options_widget)' in panel
    assert 'self._parked[target] = (process, hwnd)' in panel
    assert 'attached.detach(foreground=False, show_window=False)' in panel
    win = (SRC / 'studio_win32_host.py').read_text(encoding='utf-8')
    assert 'def restore_parked_studio_window(' in win
    assert 'if not show_window:' in win


def test_close_keeps_live_edit_state_in_memory():
    view = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    assert 'def show_option_settings_preview(' in view
    assert 'self.studio_preview.open_options(' in view
    panel = (SRC / 'studio_preview_panel.py').read_text(encoding='utf-8')
    assert '_park_current(self)' in panel
    # Studio child must NOT be killed or asked to close by the Preview close.
    assert 'window.close(' not in panel
    assert '.kill(' not in panel


def test_real_close_method_hides_pane_without_detach():
    from types import SimpleNamespace
    tree = ast.parse((SRC / 'expanded_view.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'ExpandedLauncherView')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == 'close_studio_preview')
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<closure-test>', 'exec'), namespace)

    class Panel:
        def __init__(self):
            self.hidden = False
        def isHidden(self):
            return self.hidden
        def hide(self):
            self.hidden = True
        def undock(self):
            raise AssertionError('× should never detach Studio')

    updated_sizes = []
    panel = Panel()
    splitter = SimpleNamespace(count=lambda: 4,
                               setSizes=lambda sizes: updated_sizes.append(sizes))
    view = SimpleNamespace(studio_preview=panel, files_splitter=splitter,
                           _studio_preview_base_sizes=[290, 750])
    view._hide_studio_preview_only = lambda: (setattr(panel, 'hidden', True), updated_sizes.append([290, 750, 0, 0]), setattr(view, '_studio_preview_base_sizes', None))
    namespace['close_studio_preview'](view)
    assert panel.hidden
    assert updated_sizes == [[290, 750, 0, 0]]
    assert view._studio_preview_base_sizes is None


def test_parking_old_editor_is_hidden_and_retains_process():
    from types import SimpleNamespace
    tree = ast.parse((SRC / 'studio_preview_panel.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'StudioPreviewPanel')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == '_park_current')
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<parking-test>', 'exec'), namespace)

    class Attached:
        hwnd = 98765
        def __init__(self): self.called = []
        def detach(self, **kwargs): self.called.append(kwargs)

    process = SimpleNamespace(poll=lambda: None)
    attached = Attached()
    target = ('C:/FRB/data.json', 'studio.exe', 'C:/Studio')
    obj = SimpleNamespace(_timer=SimpleNamespace(stop=lambda:None),
                          _attached=attached, _process=process,
                          _target=target, _parked={})
    namespace['_park_current'](obj)
    assert attached.called == [{'foreground': False, 'show_window': False}]
    assert obj._parked[target] == (process, 98765)
    assert obj._attached is None and obj._target is None
