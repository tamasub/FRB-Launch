"""Contracts, not per-menu Expected: one close owner and one feedback owner."""
from types import SimpleNamespace as NS
import pytest
import menu_lifecycle as ml
from processing_display import ProcessingDisplay, CURSOR, MESSAGE, PROGRESS


class Action:
    def __init__(self, child=None, enabled=True, visible=True, separator=False):
        self.child, self.enabled, self.visible, self.separator = child, enabled, visible, separator
    def menu(self): return self.child
    def isEnabled(self): return self.enabled
    def isVisible(self): return self.visible
    def isSeparator(self): return self.separator


class Menu:
    def __init__(self, name, events, *, visible=True, parent=None):
        self.name, self.events, self.visible, self.parent = name, events, visible, parent
        self.rows, self.child, self.openers = [], None, {}
    def actions(self): return self.rows
    def isVisible(self): return self.visible
    def parentWidget(self): return self.parent
    def close(self):
        self.events.append(('close', self.name))
        self.visible = False


class Application:
    def __init__(self, events): self.events = events; self.cursors = []
    def setOverrideCursor(self, cursor): self.cursors.append(cursor); self.events.append(('cursor', cursor))
    def restoreOverrideCursor(self): self.cursors.pop(); self.events.append(('restore',))
    def processEvents(self, flags): self.events.append(('paint', flags))


class Dialog:
    def __init__(self, events, mode, total):
        self.events, self.mode = events, mode
        events.append(('dialog', mode, total))
    def show(self): self.events.append(('show', self.mode))
    def close(self): self.events.append(('hide', self.mode))
    def deleteLater(self): self.events.append(('dispose', self.mode))
    def advance(self, *args): self.events.append(('advance', *args))


@pytest.fixture
def setup(monkeypatch):
    events = []
    app = Application(events)
    manager = ProcessingDisplay(app, 'wait', 'exclude',
        lambda parent, verb, total, mode: Dialog(events, mode, total))
    monkeypatch.setattr(ml, 'processing_display', lambda: manager)
    return events, app, manager


def test_terminal_classification_is_independent_of_caption():
    menu = Menu('root', [])
    leaf = Action()
    assert ml.is_terminal(menu, leaf)
    assert not ml.is_terminal(menu, Action(child=Menu('child', [])))
    assert not ml.is_terminal(menu, Action(enabled=False))
    assert not ml.is_terminal(menu, Action(visible=False))
    assert not ml.is_terminal(menu, Action(separator=True))
    assert not ml.is_terminal(menu, None)
    menu.openers[leaf] = lambda: None
    assert not ml.is_terminal(menu, leaf)
    menu.openers.clear()
    menu.folder_list_action = leaf
    assert not ml.is_terminal(menu, leaf)
    widget = Action(); widget.defaultWidget = lambda: object()
    assert not ml.is_terminal(menu, widget)


def test_close_all_owned_descendants_even_if_intermediate_hidden(setup):
    events, _, _ = setup
    root = Menu('root', events)
    child = Menu('hidden', events, visible=False, parent=root)
    grand = Menu('grand', events, parent=child)
    native = Menu('native', events)
    unrelated = Menu('unrelated', events)
    root.child = child; child.child = grand; root.rows = [Action(native)]
    root._submenus = {'also': grand}
    assert ml.selection_root(grand) is root
    ml.close_menu_tree(root)
    assert not root.visible and not grand.visible and not native.visible
    assert unrelated.visible
    assert events == [('close','grand'),('close','native'),('close','root')]


def test_close_before_callback_once_even_when_deferred(setup):
    events, app, _ = setup
    root = Menu('root', events)
    queued = []
    def work():
        assert not root.visible
        assert app.cursors == ['wait']
        events.append(('work',))
    assert ml.finish_selection(root, work, defer=queued.append)
    assert not ml.finish_selection(root, work, defer=queued.append)
    assert events == [('close','root')] and len(queued) == 1
    queued.pop()()
    assert events == [('close','root'),('cursor','wait'),('work',),('restore',)]
    ml.reset_selection(root); root.visible = True
    assert ml.finish_selection(root, work)
    assert events.count(('work',)) == 2


def test_failure_does_not_reopen_or_leak_cursor(setup):
    events, app, _ = setup
    root = Menu('root', events)
    def work(): raise RuntimeError('failed')
    with pytest.raises(RuntimeError): ml.finish_selection(root, work)
    assert not root.visible and app.cursors == []
    assert events[-1] == ('restore',)


def test_native_signal_fallback_only_closes_its_own_leaf(setup):
    events, _, _ = setup
    root = Menu('root', events); other = Menu('other', events)
    ml.close_after_native_trigger(root, Action(child=Menu('branch',events)))
    assert root.visible
    ml.close_after_native_trigger(root, Action())
    assert not root.visible and other.visible


@pytest.mark.parametrize('mode', [CURSOR, MESSAGE, PROGRESS])
def test_display_modes_share_cursor_and_cleanup(setup, mode):
    events, app, manager = setup
    with manager.display(mode, verb='test', total=3) as advance:
        assert app.cursors == ['wait']
        advance(2,3,'name')
    assert app.cursors == []
    assert events[0] == ('cursor','wait') and events[-1] == ('restore',)
    if mode == CURSOR:
        assert events == [('cursor','wait'),('restore',)]
    else:
        assert ('show',mode) in events and ('dispose',mode) in events
        assert (('advance',2,3,'name') in events) == (mode == PROGRESS)


def test_nested_progress_and_human_confirmation_restore_correctly(setup):
    events, app, manager = setup
    app.cursors.append('preexisting')
    with manager.display():
        with manager.waiting_for_user():
            assert app.cursors == ['preexisting']
        assert app.cursors == ['preexisting','wait']
        with pytest.raises(ValueError):
            with manager.display(PROGRESS, total=2):
                assert app.cursors == ['preexisting','wait']
                raise ValueError('cancelled')
        assert ('dispose',PROGRESS) in events
        assert app.cursors == ['preexisting','wait']
    assert app.cursors == ['preexisting']
    with pytest.raises(ValueError):
        with manager.display('NONE'): pass
    assert app.cursors == ['preexisting']


def test_failure_while_constructing_dialog_restores_cursor(setup):
    _, app, manager = setup
    def bad(*args, **kwargs): raise RuntimeError('display failed')
    manager.dialog_factory = bad
    with pytest.raises(RuntimeError): manager.run(lambda: None, MESSAGE)
    assert app.cursors == [] and manager.depth == 0


@pytest.mark.parametrize('mode', [MESSAGE, PROGRESS])
def test_background_work_stays_inside_shared_display(setup, monkeypatch, mode):
    import processing_display as pd
    events, app, manager = setup
    result = object()
    def worker(callback):
        assert ('show', mode) in events
        assert ('hide', mode) not in events
        assert app.cursors == ['wait']
        return callback()
    monkeypatch.setattr(pd, '_run_qt_background', worker)
    assert manager.run_background(lambda: result, mode, verb='test') is result
    assert ('dispose', mode) in events
    assert app.cursors == []
    assert manager.depth == 0


def test_background_failure_restores_cursor_and_preserves_exception(setup, monkeypatch):
    import processing_display as pd
    events, app, manager = setup
    failure = OSError('operation failed')
    def worker(callback):
        raise failure
    monkeypatch.setattr(pd, '_run_qt_background', worker)
    with manager.display(CURSOR):
        with pytest.raises(OSError) as exc:
            manager.run_background(lambda: None, MESSAGE)
        assert exc.value is failure
        assert ('dispose', MESSAGE) in events
        assert app.cursors == ['wait']
    assert app.cursors == [] and manager.depth == 0


def test_background_rejects_nonmodal_cursor_only_mode(setup, monkeypatch):
    import processing_display as pd
    events, app, manager = setup
    monkeypatch.setattr(pd, '_run_qt_background', lambda cb: pytest.fail('must not start'))
    with pytest.raises(ValueError):
        manager.run_background(lambda: None, CURSOR)
    assert events == []
