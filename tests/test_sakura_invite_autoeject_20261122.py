"""Sakura invitation: switched previews release the verified HWND and permit redock.

Pure extracted-method tests do not touch user windows. A Windows real-HWND
acceptance run remains necessary before declaring the desktop handoff final.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'


def method(filename, name, cls):
    tree = ast.parse((SRC / filename).read_text(encoding='utf-8'))
    owner = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == cls)
    meth = next(x for x in owner.body if isinstance(x, ast.FunctionDef) and x.name == name)
    ns = {'Path': Path, 'Qt': NS(FocusReason=NS(OtherFocusReason=0)),
          'QTimer': NS(singleShot=lambda ms, callback: None)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[meth], type_ignores=[])),
                 str(SRC / filename), 'exec'), ns)
    return ns[name]


def view(name):
    return method('expanded_view.py', name, 'ExpandedLauncherView')


def panel(name):
    return method('studio_preview_panel.py', name, 'StudioPreviewPanel')


class FakePanel:
    def __init__(self, *, attached=True, release=True):
        self.events = []
        self.attached = attached
        self.release = release
        self._target = None
        self._process = None
        self._studio_popout_pending = False
        self._attached = NS(is_ime_overlay=True)
    def isHidden(self): return False
    def sakura_attached(self): return self.attached
    def release_sakura_guest_for_browser(self):
        self.events.append('eject')
        if self.release:
            self.attached = False
        return self.release
    def _explain_sakura_switch_blocked(self): self.events.append('refused')
    def open_document(self, target): self.events.append(('studio', target)); return True
    def open_external(self, target): self.events.append(('external', target.app)); return True
    def open_options(self, *args): self.events.append('options'); return True


def fake_view(panel_obj):
    return NS(studio_preview=panel_obj, _workspace_mode='files',
              _ensure_studio_preview=lambda **kwargs: True,
              middle=NS(tree=NS(hasFocus=lambda: False)),
              _remember_third_column_file=lambda *a: None,
              queue_rail_wheel_position=lambda: None,
              _third_column_folder_history=NS(clear_active=lambda: None),
              _preview_maximized=False)


def test_sakura_to_studio_auto_eject_before_new_editor_is_opened():
    sakura = FakePanel()
    owner = fake_view(sakura)
    assert view('show_studio_preview')(owner, ('doc.json',))
    assert sakura.events == ['eject', ('studio', ('doc.json',))]


def test_failed_sakura_to_studio_preserves_old_window_and_does_not_open_new():
    sakura = FakePanel(release=False)
    owner = fake_view(sakura)
    assert not view('show_studio_preview')(owner, ('doc.json',))
    assert sakura.events == ['eject', 'refused']
    assert sakura.attached


def test_sakura_to_markdown_obisidian_releases_first():
    sakura = FakePanel()
    owner = fake_view(sakura)
    target = NS(app='obsidian', path='C:/docs/memo.md')
    assert view('show_external_preview')(owner, target)
    assert sakura.events == ['eject', ('external', 'obsidian')]


def test_sakura_to_vscode_releases_first():
    sakura = FakePanel()
    owner = fake_view(sakura)
    target = NS(app='vscode', path='C:/docs/code.py')
    assert view('show_external_preview')(owner, target)
    assert sakura.events == ['eject', ('external', 'vscode')]


def test_failed_handoff_is_handled_and_no_unplanned_standalone_fallback():
    sakura = FakePanel(release=False)
    owner = fake_view(sakura)
    target = NS(app='obsidian', path='C:/docs/memo.md')
    assert view('show_external_preview')(owner, target) is True
    assert sakura.events == ['eject', 'refused']
    assert sakura.attached


def test_another_sakura_file_keeps_same_docked_editor_and_does_not_eject(monkeypatch):
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    sakura = FakePanel()
    owner = fake_view(sakura)
    target = NS(app='sakura', path='C:/docs/next.txt')
    assert view('show_external_preview')(owner, target)
    assert sakura.events == [('external', 'sakura')]


def test_sakura_to_options_releases_before_opening_options():
    sakura = FakePanel()
    sakura.folder_button = NS(hide=lambda: None)
    owner = fake_view(sakura)
    assert view('show_option_settings_preview')(owner, 'home', 'state', 'root')
    assert sakura.events == ['eject', 'options']


def test_sakura_release_tracks_hwnd_and_telemetry_without_closing():
    events = []
    class Overlay:
        hwnd=321
        attached=True
        is_ime_overlay=True
        u=NS(IsWindow=lambda hwnd: hwnd == 321)
        def detach(self, **kw):
            events.append(('detach', kw))
            self.attached=False
    win=Overlay()
    key=('sakura', 'c:/docs/memo.txt')
    preview=NS(_attached=win, _external_key=key, _external_parked={},
               _external_pending=None, _sakura_guest_switch=None,
               _sakura_guest_queued=None, _external_timer=NS(stop=lambda:None),
               _sync_popout_button=lambda:None,
               _sakura_trace=lambda event, **kw:events.append((event, kw)))
    assert panel('release_sakura_guest_for_browser')(preview)
    assert win.attached is False
    assert preview._external_parked == {key: 321}
    assert ('detach', {'foreground': False, 'show_window': True}) in events
    assert [event for event, *_ in events if event != 'detach'] == [
        'AUTO_EJECT_REQUEST', 'AUTO_EJECT_DONE']


def test_same_txt_redocks_exact_verified_hwnd_after_auto_eject(monkeypatch):
    """Keep the already edited Sakura window; never spawn Sakura twice."""
    import sys
    sys.path.insert(0, str(SRC))
    import external_win32_host
    import guest_window_overlay
    import sakura_guest_bridge
    from external_preview_route import ExternalPreviewTarget

    monkeypatch.setattr(sakura_guest_bridge, 'enabled', lambda: True)
    monkeypatch.setattr(external_win32_host, 'editor_window_title',
                        lambda hwnd: 'C:/docs/001.txt - サクラエディタ' if hwnd == 321 else '')
    captured = []
    class Overlay:
        def __init__(self, hwnd, host_hwnd):
            captured.append(('attach', hwnd, host_hwnd))
            self.hwnd = hwnd
            self.attached = True
            self.is_ime_overlay = True
            self.u = NS(IsWindow=lambda h: h == 321)
        def resize(self, w, h):
            captured.append(('size', w, h))
        def detach(self, **kwargs):
            captured.append(('detach', kwargs))
            self.attached = False
    monkeypatch.setattr(guest_window_overlay, 'SakuraGuestOverlay', Overlay)

    class Label:
        def setText(self, text): pass
        def setToolTip(self, text): pass
        def hide(self): pass
    target = ExternalPreviewTarget('sakura', 'C:/docs/001.txt')
    host = NS(winId=lambda:55, width=lambda:720, height=lambda:480)
    panel_obj = NS(_attached=Overlay(321, 55), _external_key=target.key,
                   _external_parked={}, _external_pending=None,
                   _sakura_guest_switch=None, _sakura_guest_queued=None,
                   _external_timer=NS(stop=lambda:None),
                   _sync_popout_button=lambda:None,
                   _sakura_trace=lambda *a, **k:captured.append(('trace',a[0])),
                   host=host, _target=None,
                   _park_current=lambda:None,
                   content_stack=NS(setCurrentWidget=lambda w:None),
                   title_label=Label(), status_label=Label())
    assert panel('release_sakura_guest_for_browser')(panel_obj)
    assert panel_obj._external_parked[target.key] == 321
    assert panel_obj._attached is None
    # No executable launch is necessary if a verified parked window matches.
    assert panel('_open_sakura_guest')(panel_obj, target)
    assert panel_obj._attached.hwnd == 321
    assert panel_obj._external_key == target.key
    assert target.key not in panel_obj._external_parked
    assert ('trace','AUTO_REDOCK_DONE') in captured
    assert captured.count(('attach',321,55)) == 2
