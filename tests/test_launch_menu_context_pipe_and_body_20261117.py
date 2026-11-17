"""Regression for Launch Settings -> reused Studio session and native body painting."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace as NS

BASE = Path(__file__).resolve().parents[1] / 'src'
PANEL = (BASE / 'studio_preview_panel.py').read_text(encoding='utf-8')
APP = (BASE / 'app.py').read_text(encoding='utf-8')


def _method(name, **overrides):
    tree = ast.parse(PANEL)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'StudioPreviewPanel')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == name)
    scope = {'json': json, **overrides}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 '<panel>', 'exec'), scope)
    return scope[name]


class FakePipe:
    def __init__(self):
        self.written = b''
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def write(self, data): self.written += data
    def readline(self): return b'OK\n'


class InlineThread:
    def __init__(self, target, **_): self.target = target
    def start(self): self.target()


def _switch(target):
    pipe = FakePipe()
    emitted = []
    panel = NS(_launch_switch_pending=None,
               _launch_pipe_token='a' * 32,
               _process=NS(poll=lambda: None),
               status_label=NS(setText=lambda *_: None),
               _launch_switch_completed=NS(emit=lambda *args: emitted.append(args)))
    switch = _method('_switch_launch_document',
                     threading=NS(Thread=InlineThread),
                     open=lambda *_args, **_kwargs: pipe)
    assert switch(panel, target) is True
    assert emitted == [(target, 'OK')]
    return json.loads(pipe.written.decode('utf-8').strip())


def test_regular_json_reuse_has_no_launch_maintenance_authority():
    assert _switch(('C:/FRB/incidents.json', 'studio.exe', 'C:/FRB')) == {
        'path': 'C:/FRB/incidents.json', 'args': []}


def test_launch_menu_settings_reuse_carries_its_original_editor_context():
    flags = ('--launch-home=C:/FRBLaunch',
             '--launch-view-def=C:/FRBLaunch/defs/launch/frb_launch_maintenance_view_def_v0_1.json',
             '--launch-page-id=HOME')
    target = ('C:/Users/test/AppData/Local/FRBLaunch/UserData/frb_launch_data.json',
              'studio.exe', 'C:/FRBStudio', flags)
    assert _switch(target) == {'path': target[0], 'args': list(flags)}


def test_native_embedded_body_has_opaque_theme_backing():
    assert 'background:transparent; border:0;' not in APP.split('self.main_body.setStyleSheet(',1)[1].split('self.search_bar.setStyleSheet(',1)[0]
    assert 'background:{colors["window"]}' in APP
    assert 'self.update_window_shape()' in APP  # original rounding retained
