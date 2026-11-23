"""Regression: the main Launch × remains operable with Sakura docked.

The title-bar × must use the existing explicit closeEvent path. Other
non-explicit dismiss calls still protect attached Sakura from hiding Launch.
These tests inspect the actual method body without importing Windows/PySide6.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

SRC = Path(__file__).resolve().parents[1] / 'src' / 'app.py'
APP = SRC.read_text(encoding='utf-8')
ROOT = ast.parse(APP)
LAUNCHER = next(c for c in ROOT.body if isinstance(c, ast.ClassDef) and c.name == 'Launcher')


def get_method(name):
    node = next(n for n in LAUNCHER.body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(SRC), 'exec'), scope)
    return scope[name]


def test_main_close_button_invokes_explicit_qt_close_event():
    assert 'self.close_button.clicked.connect(self.close)' in APP
    assert 'self.close_button.clicked.connect(self.dismiss)' not in APP
    calls = []
    close_event = get_method('closeEvent')
    close_event(NS(dismiss=lambda **kwargs: calls.append(('dismiss', kwargs))),
                NS(ignore=lambda: calls.append(('ignore',))))
    assert calls == [('ignore',), ('dismiss', {'force': True})]


def test_non_explicit_dismiss_still_protects_attached_sakura():
    calls = []
    panel = NS(sakura_attached=lambda: True)
    close = get_method('dismiss')
    obj = NS(expanded_view=NS(studio_preview=panel),
             first_hand_confirmation_pending=lambda: False,
             isVisible=lambda: True,
             save_last_current=lambda: calls.append('save_last_current'))
    close(obj)
    assert calls == [], 'Esc/outside click must still be blocked while Sakura is docked'
