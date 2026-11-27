"""Development console readiness is based on hook registration and Qt dispatch."""
import ast
import io
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stdout

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'app.py'
MODULE = ast.parse(SOURCE.read_text(encoding='utf-8'))


def get_function(name):
    return next(n for n in MODULE.body if isinstance(n, ast.FunctionDef) and n.name == name)


def load_notice(*, frozen=False, stdout=True):
    namespace = {'sys': SimpleNamespace(frozen=frozen, stdout=object() if stdout else None)}
    exec(compile(ast.Module(body=[get_function('report_desktop_startup_ready')], type_ignores=[]),
                 str(SOURCE), 'exec'), namespace)
    return namespace['report_desktop_startup_ready']


def test_ready_message_is_flushed():
    notice = load_notice()
    calls = []
    notice.__globals__['print'] = lambda text, **kwargs: calls.append((text, kwargs))
    notice(True)
    assert len(calls) == 1
    assert '[READY]' in calls[0][0] and 'ダブルクリック' in calls[0][0]
    assert calls[0][1] == {'flush': True}


def test_failed_hook_never_announces_desktop_ready():
    stream = io.StringIO()
    with redirect_stdout(stream):
        load_notice()(False)
    assert '[WARN]' in stream.getvalue() and '[READY]' not in stream.getvalue()


def test_frozen_build_and_no_console_are_silent():
    stream = io.StringIO()
    with redirect_stdout(stream):
        load_notice(frozen=True)(True)
        load_notice(stdout=False)(True)
    assert stream.getvalue() == ''


def test_closed_console_does_not_break_startup():
    notice = load_notice()
    def broken_print(*args, **kwargs):
        raise OSError('closed console')
    notice.__globals__['print'] = broken_print
    notice(True)


def test_ascii_fallback_for_redirected_console():
    notice = load_notice()
    output = []
    def ascii_print(text, **kwargs):
        output.append(text.encode('ascii'))
    notice.__globals__['print'] = ascii_print
    notice(True)
    assert output == [b'[READY] FRB Launch - Double-click the desktop to open.']


def test_notice_is_scheduled_after_hook_and_ipc_setup_before_event_loop():
    main = get_function('main')
    statements = [ast.unparse(n) for n in main.body]
    hook = next(i for i, s in enumerate(statements) if 'desktop_hook_active = desktop_click.start()' in s)
    ipc = next(i for i, s in enumerate(statements) if 'server.newConnection.connect(wake)' in s)
    notice = next(i for i, s in enumerate(statements) if 'QTimer.singleShot(0, lambda: report_desktop_startup_ready(desktop_hook_active))' in s)
    loop = next(i for i, s in enumerate(statements) if 'result = app.exec()' in s)
    assert hook < ipc < notice < loop
    assert 'desktop_hook_active = False' in statements[hook]
    assert 'return 0' in next(s for s in statements if 'if not lock.tryLock(0)' in s)
