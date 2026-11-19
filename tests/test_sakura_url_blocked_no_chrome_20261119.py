"""Sakura -> embedded URL: auto-pop out, or consume unsafe fallback.

The file name remains historical. This is now a safe-handoff contract rather
than an unconditional URL block. Run without a Windows GUI via source AST.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'


def _method(name):
    tree = ast.parse((SRC / 'expanded_view.py').read_text(encoding='utf-8'))
    owner = next(c for c in tree.body if isinstance(c, ast.ClassDef)
                 and c.name == 'ExpandedLauncherView')
    fn = next(f for f in owner.body if isinstance(f, ast.FunctionDef)
              and f.name == name)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<sakura-browser-handoff>', 'exec'), namespace)
    return namespace[name]


def test_url_click_auto_handoff_opens_embedded_browser():
    import sys
    sys.path.insert(0, str(SRC))
    events = []
    view = NS(_workspace_mode='files',
              studio_preview=NS(isHidden=lambda: False, sakura_attached=lambda: True),
              launcher=NS(webview_settings={'mode': 'embedded'},
                          info_notice=lambda message: events.append(('notice', message))))
    view._show_browser_third_column = lambda: events.append('handoff') or True
    view.browser_preview = NS(navigate=lambda url, **kw: events.append(('navigate', url, kw)))
    assert _method('show_browser_preview')(view, 'https://example.org/a')
    assert events == ['handoff', ('navigate', 'https://example.org/a', {'new_tab': None})]


def test_failed_handoff_is_consumed_not_sent_to_chrome():
    import sys
    sys.path.insert(0, str(SRC))
    events = []
    view = NS(_workspace_mode='files',
              studio_preview=NS(isHidden=lambda: False, sakura_attached=lambda: True),
              launcher=NS(webview_settings={'mode': 'embedded'},
                          info_notice=lambda message: events.append(('notice', message))))
    view._show_browser_third_column = lambda: events.append('failed') or False
    view.browser_preview = NS(navigate=lambda *args, **kw: events.append('navigate'))
    assert _method('show_browser_preview')(view, 'https://example.org/a')
    assert events[0] == 'failed' and events[1][0] == 'notice'
    assert 'URLは開いていません' in events[1][1]
    assert 'navigate' not in events


def test_invalid_url_never_enters_handoff():
    import sys
    sys.path.insert(0, str(SRC))
    events = []
    view = NS(_workspace_mode='files',
              studio_preview=NS(isHidden=lambda: False, sakura_attached=lambda: True),
              launcher=NS(webview_settings={'mode': 'embedded'},
                          info_notice=lambda message: events.append(message)),
              _show_browser_third_column=lambda: events.append('handoff'))
    assert not _method('show_browser_preview')(view, 'javascript:alert(1)')
    assert not events


def test_file_list_uses_true_for_handled_preview():
    source = (SRC / 'expanded_view.py').read_text(encoding='utf-8')
    assert 'callable(preview) and preview(row)):' in source
    assert 'return bool(self.launcher.preview_authored_launch_url(virtual.get(\'row\')))' in source
    assert 'return True  # Refusal consumed: never launch Chrome.' in source
