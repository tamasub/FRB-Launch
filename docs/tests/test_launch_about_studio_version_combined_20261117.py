"""Version 0.9.12 About URL and 2026-11-17 Studio version coexist."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from app_version import APP_VERSION, APP_REPOSITORY_URL
from studio_version import read_studio_version


def _init_body():
    source = (ROOT / 'src' / 'update_information_dialog.py').read_text('utf-8')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'UpdateInformationDialog')
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == '__init__')
    return source, init.body


def test_launch_version_kept_at_0912():
    assert APP_VERSION == '0.9.12'
    assert APP_REPOSITORY_URL == 'https://github.com/tamasub/FRB-Launch'


def test_studio_version_and_repository_url_both_present():
    source, body = _init_body()
    assert 'from studio_version import read_studio_version' in source
    assert 'from app_version import APP_REPOSITORY_URL' in source
    assert 'read_studio_version(self.launch_home, self.install_root, studio_root)' in source
    assert "studio_label = studio_version" in source
    assert "'（配布記録）'" in source
    assert 'setOpenExternalLinks(True)' in source
    assert 'setTextFormat(Qt.TextFormat.RichText)' in source
    assert 'setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)' in source
    assert 'self.resize(435,320)' in source
    start = source.index('self.studio_component=QLabel(')
    link = source.index('lay.addWidget(self.repository_link)')
    buttons = source.index('lay.addLayout(buttons)')
    assert start < link < buttons
    assert source.count('lay.addWidget(self.repository_link)') == 1


def test_real_repository_widget_statements_open_external_link():
    # Real statements, but with fake Qt controls; no PySide6 import needed.
    _, body = _init_body()
    def has_call(stmt, name):
        return (isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == name)
    start = next(i for i, stmt in enumerate(body) if has_call(stmt,'addStretch'))
    end = next(i for i, stmt in enumerate(body[start:], start)
               if has_call(stmt, 'addWidget') and 'self.repository_link' in ast.unparse(stmt))

    class Label:
        def __init__(self, text): self.text = text
        def setObjectName(self, name): self.name = name
        def setTextFormat(self, value): self.format = value
        def setTextInteractionFlags(self, value): self.flags = value
        def setOpenExternalLinks(self, value): self.external = value
    class Layout:
        def __init__(self): self.widgets = []
        def addStretch(self, v): self.stretch = v
        def addWidget(self, v): self.widgets.append(v)

    qt=SimpleNamespace(TextFormat=SimpleNamespace(RichText='rich'),
                       TextInteractionFlag=SimpleNamespace(TextBrowserInteraction='browser'))
    scope={'self':SimpleNamespace(),'lay':Layout(),'QLabel':Label,
           'Qt':qt,'APP_REPOSITORY_URL':APP_REPOSITORY_URL}
    module=ast.fix_missing_locations(ast.Module(body=body[start:end+1],type_ignores=[]))
    exec(compile(module,'update_information_dialog.py','exec'),scope)
    label=scope['self'].repository_link
    assert scope['lay'].widgets==[label]
    assert label.name=='updateRepositoryLink'
    assert f'href="{APP_REPOSITORY_URL}"' in label.text
    assert label.external is True
    assert label.format=='rich' and label.flags=='browser'


def test_launch_passes_configured_studio_root_to_dialog():
    caller=(ROOT/'src/app.py').read_text('utf-8')
    assert "studio_root=self.expander().values.get('studio_root', '')" in caller
    assert 'dialog = UpdateInformationDialog(' in caller


def test_studio_version_still_reads_metadata(tmp_path):
    launch=tmp_path/'Launch'; studio=tmp_path/'MyStudio'
    (studio/'defs').mkdir(parents=True)
    (studio/'defs/app_version.json').write_text(
        '{"app_name":"FRB Studio","app_version":"0.9.0"}', encoding='utf-8')
    assert read_studio_version(launch, launch, studio)=='0.9.0'
