"""Thread/result contract tests without PySide6; Qt rendering has separate tests."""
import queue
import sys
import threading
from types import ModuleType, SimpleNamespace as NS

import pytest
from processing_display import _run_qt_background


@pytest.fixture
def fake_qt(monkeypatch):
    main = threading.current_thread()
    queued = queue.Queue()
    lifecycle = []
    class Signal:
        def connect(self, callback, kind):
            assert kind == 'queued'
            self.callback = callback
        def emit(self):
            queued.put(self.callback)
    class Thread:
        @staticmethod
        def currentThread():
            return threading.current_thread()
        def __init__(self):
            self.finished = Signal()
        def start(self):
            def entry():
                try:
                    self.run()
                finally:
                    self.finished.emit()
            self.thread = threading.Thread(target=entry)
            self.thread.start()
            lifecycle.append('started')
        def wait(self):
            self.thread.join(3)
            assert not self.thread.is_alive()
            lifecycle.append('joined')
    class Loop:
        def exec(self):
            lifecycle.append('loop')
            self.done = False
            while not self.done:
                queued.get(timeout=3)()
        def quit(self):
            assert threading.current_thread() is main
            self.done = True
    qtcore = ModuleType('PySide6.QtCore')
    qtcore.QThread = Thread
    qtcore.QEventLoop = Loop
    qtcore.QCoreApplication = NS(instance=lambda: NS(thread=lambda: main))
    qtcore.Qt = NS(ConnectionType=NS(QueuedConnection='queued'))
    monkeypatch.setitem(sys.modules, 'PySide6.QtCore', qtcore)
    return main, lifecycle


def test_fast_background_result_and_thread_join(fake_qt):
    main, lifecycle = fake_qt
    for _ in range(12):
        assert _run_qt_background(threading.current_thread) is not main
    assert lifecycle == ['started', 'loop', 'joined'] * 12


def test_worker_failure_is_returned_as_original_exception(fake_qt):
    _, lifecycle = fake_qt
    failure = OSError('git failure')
    def fail():
        raise failure
    with pytest.raises(OSError) as caught:
        _run_qt_background(fail)
    assert caught.value is failure
    assert lifecycle == ['started', 'loop', 'joined']


def test_background_entry_requires_gui_thread(fake_qt):
    _, lifecycle = fake_qt
    result = []
    def outside():
        try:
            _run_qt_background(lambda: None)
        except RuntimeError as exc:
            result.append(str(exc))
    thread = threading.Thread(target=outside)
    thread.start()
    thread.join(3)
    assert not thread.is_alive()
    assert len(result) == 1 and 'GUI thread' in result[0]
    assert lifecycle == []
