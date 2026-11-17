"""RoundRailWheelPad 描画回帰: import漏れとQPainterリークを防ぐ。PySide6不要。"""
import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REMOTE = ROOT / 'src' / 'launch_remote.py'


def _method_ast():
    tree = ast.parse(REMOTE.read_text(encoding='utf-8'))
    core_imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                    and node.module == 'PySide6.QtCore']
    assert any(item.name == 'QPointF' for imp in core_imports for item in imp.names), 'QPointF import is required for center divider and hover dot'
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'RoundRailWheelPad')
    return next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name == 'paintEvent')


def _simulate_paint(fail_on=None, hover=None):
    """実際のpaintEvent本文を簡易Qt部品とともに実行する。"""
    method = _method_ast()
    executions = []

    class FakeColor:
        def __init__(self, value):
            self.value = value

        def setAlpha(self, alpha):
            pass

    class FakeFont:
        Weight = SimpleNamespace(DemiBold=1, Medium=2)

        def __init__(self, orig):
            pass

        def setPixelSize(self, pixels):
            pass

        def setWeight(self, weight):
            pass

    class FakePainter:
        RenderHint = SimpleNamespace(Antialiasing=1)

        def __init__(self, owner):
            executions.append('begin')

        def setRenderHint(self, *args):
            pass

        def setPen(self, *args):
            pass

        def setBrush(self, *args):
            pass

        def setFont(self, *args):
            pass

        def drawEllipse(self, *args):
            executions.append('ellipse')

        def drawLine(self, *args):
            executions.append('line')
            if fail_on == 'line':
                raise RuntimeError('simulated Qt painter failure')

        def drawText(self, *args):
            executions.append('text')

        def end(self):
            executions.append('end')

    namespace = dict(
        QPainter=FakePainter,
        QColor=FakeColor,
        QFont=FakeFont,
        QRectF=lambda *a: a,
        QPointF=lambda *a: a,
        QPen=lambda *a: a,
        Qt=SimpleNamespace(
            PenStyle=SimpleNamespace(DotLine=1, NoPen=2),
            PenCapStyle=SimpleNamespace(RoundCap=1),
            AlignmentFlag=SimpleNamespace(AlignCenter=1),
        ),
    )
    fragment = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(fragment, str(REMOTE), 'exec'), namespace)

    owner = SimpleNamespace(
        width=lambda: 52,
        height=lambda: 52,
        font=lambda: None,
        _circle_fill=FakeColor('fill'),
        _circle_outline=FakeColor('outline'),
        _circle_ink=FakeColor('ink'),
        _hover_side=hover,
    )
    try:
        namespace['paintEvent'](owner, None)
    except RuntimeError:
        if fail_on != 'line':
            raise
    return executions


def test_paint_normal_renders_separator_and_labels_and_ends():
    calls = _simulate_paint(hover='files_exp')
    assert 'line' in calls
    assert calls.count('text') == 3  # ぐりぐり / Exp / List
    assert calls[-1] == 'end'


def test_painter_is_ended_even_when_drawing_raises():
    calls = _simulate_paint(fail_on='line', hover='directory')
    assert calls[-1] == 'end'
    assert calls.count('end') == 1
