"""Regression contract: first NativeShell docking must not punch a hole in Launch.

Qt-free tests check the exact native-host flags and the frame refresh path.
Windows DWM visual verification remains a separate manual test.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = (ROOT / 'src' / 'studio_preview_panel.py').read_text('utf-8')
APP = (ROOT / 'src' / 'app.py').read_text('utf-8')


def _class_method(source, class_name, method_name):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
    return method


def _isolated_method(source, class_name, method_name):
    method = _class_method(source, class_name, method_name)
    isolated = ast.Module(body=[method], type_ignores=[])
    scope = {}
    exec(compile(ast.fix_missing_locations(isolated), 'preview_probe', 'exec'), scope)
    return scope[method_name]


def test_native_host_does_not_force_qt_ancestors_to_be_native_windows():
    method = _class_method(PREVIEW, '_NativeHost', '__init__')
    body = ast.get_source_segment(PREVIEW, method)
    guard = 'WA_DontCreateNativeAncestors, True'
    own = 'WA_NativeWindow, True'
    assert guard in body and own in body
    assert body.index(guard) < body.index(own)


def test_first_attach_queues_frame_refresh_after_win32_attachment():
    body = ast.get_source_segment(PREVIEW, _class_method(PREVIEW, 'StudioPreviewPanel', '_poll'))
    assert 'AttachedStudioWindow(hwnd, int(self.host.winId()))' in body
    assert 'QTimer.singleShot(0, self._refresh_outer_frame_after_native_attach)' in body
    assert body.index('AttachedStudioWindow') < body.index('_refresh_outer_frame_after_native_attach')


def test_frame_refresh_reapplies_mask_without_touching_geometry_or_data():
    refresh = _isolated_method(PREVIEW, 'StudioPreviewPanel', '_refresh_outer_frame_after_native_attach')
    launcher = SimpleNamespace(
        isVisible=lambda: True, _size_drag=None,
        clearMask=Mock(), update_window_shape=Mock(), update=Mock())
    refresh(SimpleNamespace(launcher=launcher))
    launcher.clearMask.assert_called_once_with()
    launcher.update_window_shape.assert_called_once_with()
    launcher.update.assert_called_once_with()


def test_frame_refresh_does_not_interfere_with_active_resize_or_hidden_launch():
    refresh = _isolated_method(PREVIEW, 'StudioPreviewPanel', '_refresh_outer_frame_after_native_attach')
    for visible, dragging in [(False, None), (True, ('right',))]:
        launcher = SimpleNamespace(
            isVisible=lambda: visible, _size_drag=dragging,
            clearMask=Mock(), update_window_shape=Mock(), update=Mock())
        refresh(SimpleNamespace(launcher=launcher))
        launcher.clearMask.assert_not_called()
        launcher.update_window_shape.assert_not_called()
        launcher.update.assert_not_called()


def test_outer_frame_paints_opaque_backstop_before_outline():
    method = _class_method(APP, 'Launcher', 'paintEvent')
    source = ast.get_source_segment(APP, method)
    fill = 'painter.fillRect(self.rect(), QColor(fill))'
    assert fill in source
    assert source.index(fill) < source.index('painter.drawRoundedRect(outer,')
