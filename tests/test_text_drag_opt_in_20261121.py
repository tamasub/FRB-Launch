"""Legacy Qt URL and native Windows Shell file drag branch tests."""
import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def _fake_file_drag(monkeypatch):
    drops = []
    class Mime:
        def __init__(self):
            self.urls = None
            self.data = {}
        def setUrls(self, urls): self.urls = urls
        def setData(self, label, value): self.data[label] = value
    class Drag:
        def __init__(self, widget):
            self.widget = widget
            self.mime = None
            drops.append(self)
        def setMimeData(self, mime): self.mime = mime
        def exec(self, *args): self.actions = args
    for name in ('PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    qt = SimpleNamespace(ItemDataRole=SimpleNamespace(UserRole=32),
                         DropAction=SimpleNamespace(CopyAction=1))
    sys.modules['PySide6.QtCore'].Qt = qt
    sys.modules['PySide6.QtCore'].QMimeData = Mime
    sys.modules['PySide6.QtCore'].QUrl = SimpleNamespace(fromLocalFile=lambda path: ('file', path))
    sys.modules['PySide6.QtGui'].QDrag = Drag
    sys.modules['PySide6.QtWidgets'].QTreeWidget = type('Tree', (), {})
    sys.modules['PySide6.QtWidgets'].QAbstractItemView = SimpleNamespace(
        SelectionMode=SimpleNamespace(ExtendedSelection=2))
    spec = importlib.util.spec_from_file_location('_file_drag_shell_trial', ROOT / 'src' / 'file_drag.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, drops


def _row(file):
    return {'item_kind': 'command', '_browse_file': str(file)}


def test_default_path_does_not_load_or_use_shell(monkeypatch, tmp_path):
    module, drops = _fake_file_drag(monkeypatch)
    shell = ModuleType('native_shell_drag')
    shell.begin_native_shell_file_drag = lambda *_args: (_ for _ in ()).throw(AssertionError('called'))
    monkeypatch.setitem(sys.modules, 'native_shell_drag', shell)
    p = tmp_path / '日本語.txt'
    p.write_text('日本語本文', encoding='utf-8')
    assert module.begin_file_copy_drag(object(), _row(p))
    assert drops[-1].mime.urls == [('file', str(p.resolve()))]
    assert drops[-1].mime.data['application/x-qt-windows-mime;value="Preferred DropEffect"'] == b'\x01\x00\x00\x00'
    assert drops[-1].actions == (1, 1)


def test_opt_in_calls_native_shell_and_does_not_start_qt_drag(monkeypatch, tmp_path):
    module, drops = _fake_file_drag(monkeypatch)
    calls = []
    shell = ModuleType('native_shell_drag')
    shell.begin_native_shell_file_drag = lambda widget, paths: calls.append(paths) or True
    monkeypatch.setitem(sys.modules, 'native_shell_drag', shell)
    p = tmp_path / 'test.txt'
    p.write_text('a', encoding='utf-8')
    assert module.begin_file_copy_drag(object(), _row(p), native_shell_mode=True)
    assert calls == [[str(p.resolve())]]
    assert not drops  # Native-only, no duplicate Qt drag after user cancel.


def test_opt_in_preparation_failure_falls_back_to_urls(monkeypatch, tmp_path):
    module, drops = _fake_file_drag(monkeypatch)
    shell = ModuleType('native_shell_drag')
    def fail(*_args):
        raise OSError('native shell unavailable')
    shell.begin_native_shell_file_drag = fail
    monkeypatch.setitem(sys.modules, 'native_shell_drag', shell)
    p = tmp_path / 'a.log'
    p.write_text('log')
    assert module.begin_file_copy_drag(object(), _row(p), native_shell_mode=True)
    assert drops[-1].mime.urls == [('file', str(p.resolve()))]


def test_multiple_paths_keep_order_in_shell_mode(monkeypatch, tmp_path):
    module, drops = _fake_file_drag(monkeypatch)
    calls = []
    shell = ModuleType('native_shell_drag')
    shell.begin_native_shell_file_drag = lambda _widget, paths: calls.append(paths) or True
    monkeypatch.setitem(sys.modules, 'native_shell_drag', shell)
    a, b = tmp_path / 'a.md', tmp_path / 'b.md'
    a.write_text('a')
    b.write_text('b')
    module.begin_file_copy_drag(object(), [_row(b), _row(a)], native_shell_mode=True)
    assert calls == [[str(b.resolve()), str(a.resolve())]]
    assert not drops


def test_files_list_uses_ini_policy_without_toggle():
    view = (ROOT / 'src' / 'expanded_view.py').read_text(encoding='utf-8')
    drag = (ROOT / 'src' / 'file_drag.py').read_text(encoding='utf-8')
    native = (ROOT / 'src' / 'native_shell_drag.py').read_text(encoding='utf-8')
    for code in (view, drag, native):
        ast.parse(code)
    assert 'files_list_shell_drag_enabled(' in view
    assert 'self.middle.tree.native_shell_drag_mode = files_list_shell_drag_enabled(' in view
    assert 'shell_drag_button' not in view
    assert 'set_shell_drag_mode' not in view
    assert 'self.native_shell_drag_mode = False' in drag  # non-Files List callers unchanged
    assert "native_shell_mode=getattr(self, 'native_shell_drag_mode', False)" in drag
    assert 'text_for_drag' not in drag
    assert 'text/plain' not in drag
    assert 'SHDoDragDrop' in native and 'BindToHandler' in native
