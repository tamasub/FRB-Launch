"""Files List -> Exp context switch must transfer NATIVE Qt keyboard focus.

The previous implementation changed the highlighted logical area but left
actual key events in Files List.  This Qt-free test exercises the real
Launcher dispatch function with focus-aware widget doubles.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SRC = Path(__file__).resolve().parents[1] / 'src' / 'app.py'
CODE = SRC.read_text(encoding='utf-8')


def dispatch_method(env):
    launch_cls = next(node for node in ast.parse(CODE).body
                      if isinstance(node, ast.ClassDef) and node.name == 'Launcher')
    fn = next(node for node in launch_cls.body
              if isinstance(node, ast.FunctionDef)
              and node.name == '_dispatch_files_column_context_navigation')
    ns = dict(env)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(SRC), 'exec'), ns)
    return ns[fn.name]


def simulate(*, standalone=False, target='files_exp', exp_visible=True):
    state = NS(logical='directory', keyboard='list', active_window='launch',
               positions=[], log=[], jobs=[])

    class ExpTree:
        def isVisible(self):
            return exp_visible

        def setFocus(self, reason):
            assert reason == 42
            state.keyboard = 'exp'
            state.log.append('exp-native-focus')

    class ExpPanel:
        tree = ExpTree()

        def isWindow(self):
            return standalone

        def activateWindow(self):
            state.active_window = 'exp-tool'
            state.log.append('activate-exp-tool')

    def logical_focus(area):
        state.logical = area
        state.log.append('logical:' + area)

    owner = NS(
        _remote_context_wheel=None,
        pointer_warp_enabled=False,
        remote_focus_area=logical_focus,
        _current_remote_files_exp=lambda: ExpPanel(),
    )
    menu = NS(close=lambda: state.log.append('menu-closed'))
    fn = dispatch_method({
        'Qt': NS(FocusReason=NS(ShortcutFocusReason=42)),
        'QTimer': NS(singleShot=lambda _ms, cb: state.jobs.append(cb)),
    })
    fn(owner, menu, target)
    assert state.log == ['menu-closed']  # Focus only after popup teardown.
    while state.jobs:
        state.jobs.pop(0)()
    return state


def test_list_back_to_embedded_exp_restores_arrow_key_owner():
    state = simulate()
    assert state.logical == 'files_exp'
    assert state.keyboard == 'exp'  # Next Up/Down belongs to Exp, not List.
    assert state.active_window == 'launch'
    assert state.log == ['menu-closed', 'logical:files_exp', 'exp-native-focus']


def test_list_back_to_standalone_exp_activates_its_window_before_focus():
    state = simulate(standalone=True)
    assert state.logical == 'files_exp'
    assert state.keyboard == 'exp'
    assert state.active_window == 'exp-tool'
    assert state.log == ['menu-closed', 'logical:files_exp',
                         'activate-exp-tool', 'exp-native-focus']


def test_forward_to_list_does_not_touch_exp_native_focus():
    state = simulate(target='directory')
    assert state.logical == 'directory'
    assert state.keyboard == 'list'
    assert state.log == ['menu-closed', 'logical:directory']


def test_hidden_exp_is_not_activated():
    state = simulate(standalone=True, exp_visible=False)
    assert state.logical == 'files_exp'
    assert state.keyboard == 'list'
    assert state.log == ['menu-closed', 'logical:files_exp']


def test_windows_menu_key_disable_stays_in_place():
    # Focus repair must not roll back the independent MenuKey suppression.
    assert "event.key() == getattr(Qt.Key, 'Key_Menu', None)" in CODE
