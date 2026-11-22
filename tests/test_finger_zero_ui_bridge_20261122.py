"""Qt-free extracted-method tests for routing keypad presses through Qt UI."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / 'src' / 'expanded_view.py'


def extract(name, env):
    parsed = ast.parse(VIEW.read_text(encoding='utf-8'))
    cls = next(n for n in parsed.body if isinstance(n, ast.ClassDef)
               and n.name == 'ExpandedLauncherView')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == name)
    code = compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                   str(VIEW), 'exec')
    ns = dict(env)
    exec(code, ns)
    return ns[name]


class QWidget:
    def __init__(self, window):
        self._window = window
    def window(self):
        return self._window


class QDialog(QWidget):
    pass


class Event:
    def __init__(self, kind, key, *, vk=0, modifiers=0, repeat=False):
        self.kind, self.k, self.vk = kind, key, vk
        self.mods, self.repeat = modifiers, repeat
        self.accepted = False
    def type(self): return self.kind
    def key(self): return self.k
    def modifiers(self): return self.mods
    def nativeVirtualKey(self): return self.vk
    def isAutoRepeat(self): return self.repeat
    def accept(self): self.accepted = True


def make_bridge():
    from sys import path
    path.insert(0, str(ROOT / 'src'))
    from finger_zero_keys import finger_zero_action
    sent = []
    toggles = []
    qt = NS(Key=NS(Key_Return=1001, Key_Tab=1002), KeyboardModifier=NS(NoModifier=0))
    qevent = NS(Type=NS(KeyPress=10, KeyRelease=11))
    fake_app = NS(sendEvent=lambda target, event: sent.append((target, event)))
    bridge = extract('_finger_zero_keyboard', {
        'QEvent': qevent, 'Qt': qt, 'QApplication': fake_app,
        'QWidget': QWidget, 'QDialog': QDialog,
        'finger_zero_action': finger_zero_action,
        'QKeyEvent': lambda kind, key, mods: NS(kind=kind, key=key, mods=mods),
    })
    owner = NS(_launch_owns_keyboard_source=lambda obj: True,
               _finger_zero_is_text_entry=lambda obj: False,
               launcher=NS(toggle_slash_exp_shortcut=lambda: toggles.append('slash')))
    return bridge, owner, sent, toggles, qt, qevent


def test_numpad_zero_reuses_enter_routing_once():
    fn, owner, sent, toggles, qt, types = make_bridge()
    view = QWidget(QWidget(None))
    event = Event(types.Type.KeyPress, 0x30, vk=0x60)
    assert fn(owner, view, event) and event.accepted
    assert len(sent) == 1 and sent[0][0] is view
    assert sent[0][1].key == qt.Key.Key_Return
    assert not toggles
    release = Event(types.Type.KeyRelease, 0x30, vk=0x60)
    assert fn(owner, view, release) and release.accepted
    assert len(sent) == 1, 'Key release cannot execute a second time'
    repeat = Event(types.Type.KeyPress, 0x30, vk=0x60, repeat=True)
    assert fn(owner, view, repeat) and len(sent) == 1


def test_one_tabs_only_inside_dialog_even_from_editor():
    fn, owner, sent, _, qt, types = make_bridge()
    editor = QWidget(QDialog(None))
    assert fn(owner, editor, Event(types.Type.KeyPress, 0x31, vk=0x61))
    assert sent[0][1].key == qt.Key.Key_Tab
    outside = QWidget(QWidget(None))
    assert fn(owner, outside, Event(types.Type.KeyPress, 0x31, vk=0x61)) is False
    assert len(sent) == 1


def test_zero_keeps_number_when_editor_is_focused():
    fn, owner, sent, _, _, types = make_bridge()
    owner._finger_zero_is_text_entry = lambda obj: True
    editor = QWidget(QDialog(None))
    assert fn(owner, editor, Event(types.Type.KeyPress, 0x30, vk=0x60)) is False
    assert sent == []


def test_menu_key_uses_slash_and_never_injects_right_click():
    fn, owner, sent, toggles, _, types = make_bridge()
    pane = QWidget(QWidget(None))
    assert fn(owner, pane, Event(types.Type.KeyPress, 0x01000055, vk=0x5D))
    assert toggles == ['slash']
    assert sent == []
    # Events outside Launcher-owned widgets are never modified.
    owner._launch_owns_keyboard_source = lambda obj: False
    assert fn(owner, pane, Event(types.Type.KeyPress, 0x01000055, vk=0x5D)) is False
    assert toggles == ['slash']
