"""Sakura -> URL -> same Sakura HWND, and persistent VS Code settings.

Source-AST harness: runnable without Windows/PySide6; final Win32 behavior
must still be verified with a live app. No HWND is taken from desktop tests.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'src'
sys.path.insert(0, str(SRC))


def _method(source, name, class_name):
    tree = ast.parse((SRC/source).read_text(encoding='utf-8'))
    owner = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name==class_name)
    fun = next(f for f in owner.body if isinstance(f, ast.FunctionDef) and f.name==name)
    ns = {'Path': Path}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fun], type_ignores=[])),
                 '<extracted>', 'exec'), ns)
    return ns[name]


def _studio(name):
    return _method('studio_preview_panel.py', name, 'StudioPreviewPanel')


def _view(name):
    return _method('expanded_view.py', name, 'ExpandedLauncherView')


class Timer:
    def __init__(self): self.stopped=0
    def stop(self): self.stopped+=1


class Guest:
    def __init__(self, hwnd=100, *, fails=False):
        self.hwnd=hwnd
        self.attached=True
        self.is_ime_overlay=True
        self.fails=fails
        self.u=NS(IsWindow=lambda h: True)
        self.detaches=[]
    def detach(self, **kwargs):
        self.detaches.append(kwargs)
        if not self.fails:
            self.attached=False


def test_auto_releases_sakura_without_closing_or_losing_reentry_key():
    attached=Guest()
    key=('sakura', 'c:/docs/001.txt')
    preview=NS(_attached=attached, _external_key=key, _external_parked={},
               _external_pending=None, _sakura_guest_switch=None,
               _sakura_guest_queued=None, _external_timer=Timer(),
               _sync_popout_button=lambda: None)
    assert _studio('release_sakura_guest_for_browser')(preview) is True
    assert attached.detaches==[{'foreground':False,'show_window':True}]
    assert preview._external_parked[key]==100
    assert preview._attached is None and preview._external_key is None
    assert preview._external_timer.stopped==1


def test_failed_release_does_not_discard_editor_or_navigate():
    guest=Guest(fails=True)
    key=('sakura','c:/docs/001.txt')
    preview=NS(_attached=guest, _external_key=key, _external_parked={},
               _external_pending=None, _sakura_guest_switch=None,
               _sakura_guest_queued=None, _external_timer=Timer(),
               _sync_popout_button=lambda: None)
    assert not _studio('release_sakura_guest_for_browser')(preview)
    assert preview._attached is guest and preview._external_key==key
    assert preview._external_parked=={}


def test_sakura_handoff_refused_during_tab_switch_without_detaching():
    guest=Guest()
    preview=NS(_attached=guest, _external_key=('sakura','x'), _external_parked={},
               _external_pending=None, _sakura_guest_switch=('target', 0, 0),
               _sakura_guest_queued=None)
    assert not _studio('release_sakura_guest_for_browser')(preview)
    assert guest.detaches==[]


def test_browser_switch_calls_release_and_hides_only_after_success():
    events=[]
    studio=NS(isHidden=lambda: False,
              sakura_attached=lambda: True,
              release_sakura_guest_for_browser=lambda: events.append('release') or True)
    preview=NS(_workspace_mode='files', studio_preview=studio,
               _preview_maximized=False, _preview_normal_columns=None,
               _ensure_web_view=lambda: False,
               _hide_studio_preview_only=lambda: events.append('hide'))
    assert not _view('_show_browser_third_column')(preview)
    assert events==['release','hide']


def test_browser_refuses_to_hide_sakura_if_release_fails():
    events=[]
    studio=NS(isHidden=lambda: False, sakura_attached=lambda: True,
              release_sakura_guest_for_browser=lambda: events.append('refused') or False)
    preview=NS(_workspace_mode='files', studio_preview=studio,
               _preview_maximized=False, _preview_normal_columns=None,
               _ensure_web_view=lambda: events.append('web') or True,
               _hide_studio_preview_only=lambda: events.append('hide'))
    assert not _view('_show_browser_third_column')(preview)
    assert events==['refused']


def test_failed_url_switch_is_handled_without_chrome_fallback():
    events=[]
    studio=NS(isHidden=lambda: False, sakura_attached=lambda: True)
    preview=NS(_workspace_mode='files', studio_preview=studio,
               launcher=NS(webview_settings={'mode':'embedded'},
                           info_notice=lambda m: events.append(('notice',m))),
               _show_browser_third_column=lambda: events.append('try') or False,
               browser_preview=NS(navigate=lambda *a, **k: events.append('navigate')))
    assert _view('show_browser_preview')(preview, 'https://example.org')
    assert events[0]=='try'
    assert len(events)==2 and events[1][0]=='notice'


def test_auto_release_then_url_is_navigated():
    events=[]
    studio=NS(isHidden=lambda: False,sakura_attached=lambda: True)
    preview=NS(_workspace_mode='files', studio_preview=studio,
               launcher=NS(webview_settings={'mode':'embedded'},
                           info_notice=lambda m: events.append('notice')),
               _show_browser_third_column=lambda: events.append('release->browser') or True,
               browser_preview=NS(navigate=lambda *a, **k: events.append(('navigate',a[0]))))
    assert _view('show_browser_preview')(preview,'https://example.org')
    assert events==['release->browser',('navigate','https://example.org')]


def test_vscode_profile_stable_but_not_regular_user_data(monkeypatch, tmp_path):
    import vscode_guest_bridge as code
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    assert code.new_profile_root()==code.new_profile_root()
    profile=code.new_profile_root()
    assert profile == tmp_path/'FRBLaunch'/'VSCodeGuest'/'profile-v1'
    assert profile != tmp_path/'Code'/'User'
    assert '--user-data-dir' in code.command('Code.exe',profile,'foo.py')


def test_redock_exact_sakura_desktop_hwnd_without_relaunch(monkeypatch):
    """URL has released an identified HWND; the same TXT restores it."""
    from external_preview_route import ExternalPreviewTarget
    import external_win32_host, guest_window_overlay, sakura_guest_bridge
    monkeypatch.setenv('FRB_SAKURA_GUEST_OVERLAY', '1')
    monkeypatch.setattr(external_win32_host, 'editor_window_title',
                        lambda h: 'C:/docs/001.txt - サクラエディタ' if h == 100 else '')
    class Overlay(Guest):
        def __init__(self, hwnd, host_hwnd):
            super().__init__(hwnd)
            self.sizes=[]
        def resize(self, w, h): self.sizes.append((w,h))
    monkeypatch.setattr(guest_window_overlay, 'SakuraGuestOverlay', Overlay)
    class Label:
        def __init__(self): self.value=''
        def setText(self, s): self.value=s
        def setToolTip(self, s): self.tip=s
        def hide(self): pass
    key=('sakura','c:/docs/001.txt')
    panel=NS(_attached=None, _external_key=None, _target=None,
             _external_parked={key:100}, _external_pending=None,
             _sakura_guest_switch=None, _sakura_guest_queued=None,
             _external_timer=Timer(),
             _park_current=lambda: None,
             host=NS(winId=lambda:2,width=lambda:900,height=lambda:600),
             content_stack=NS(setCurrentWidget=lambda _:None),
             title_label=Label(), status_label=Label(),
             _sync_popout_button=lambda:None)
    target=ExternalPreviewTarget('sakura','C:/docs/001.txt')
    assert _studio('_open_sakura_guest')(panel,target)
    assert panel._attached.hwnd==100 and panel._attached.attached
    assert panel._external_key==target.key
    assert key not in panel._external_parked
    assert panel._attached.sizes==[(900,600)]
