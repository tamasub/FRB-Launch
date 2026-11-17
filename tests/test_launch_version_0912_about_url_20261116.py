"""FRB Launch 0.9.12: visible Settings -> version dialog + URL (no Qt required)."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from app_version import APP_VERSION, APP_REPOSITORY_URL, APP_ABOUT_TEXT


def test_launch_version_is_defined_once_in_app_version():
    assert APP_VERSION == '0.9.12'
    assert APP_REPOSITORY_URL == 'https://github.com/tamasub/FRB-Launch'
    assert f'Version {APP_VERSION}' in APP_ABOUT_TEXT


def test_settings_version_action_uses_update_information_dialog():
    app = (ROOT / 'src' / 'app.py').read_text(encoding='utf-8')
    assert 'self.theme_update_action.triggered.connect(self.show_update_information)' in app
    assert 'dialog = UpdateInformationDialog(LAUNCH_HOME, install_root,' in app
    assert 'APP_VERSION, self.color_theme, self)' in app


def test_active_version_dialog_places_clickable_url_just_above_buttons():
    source = (ROOT / 'src' / 'update_information_dialog.py').read_text('utf-8')
    tree = ast.parse(source)
    assert 'from app_version import APP_REPOSITORY_URL' in source
    assert 'APP_REPOSITORY_URL' in source
    assert 'setOpenExternalLinks(True)' in source
    assert 'setTextFormat(Qt.TextFormat.RichText)' in source
    assert 'setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)' in source
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'UpdateInformationDialog')
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == '__init__')
    code = ast.get_source_segment(source, init)
    assert code.index('lay.addStretch(1)') < code.index('lay.addWidget(self.repository_link)')
    assert code.index('lay.addWidget(self.repository_link)') < code.index('lay.addLayout(buttons)')
    assert code.index('self.launch_component=QLabel(\'Launch: \'+launch_version)') < code.index('lay.addWidget(self.repository_link)')


def test_link_widget_builds_html_and_enables_external_clicks_without_qt():
    """Execute the real QLabel construction statements with tiny Qt stand-ins."""
    from types import SimpleNamespace

    source = (ROOT / 'src' / 'update_information_dialog.py').read_text('utf-8')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'UpdateInformationDialog')
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == '__init__')
    def is_call(stmt, name):
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            return False
        return isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == name
    start = next(i for i, stmt in enumerate(init.body) if is_call(stmt, 'addStretch'))
    end = next(i for i, stmt in enumerate(init.body[start:], start)
               if is_call(stmt, 'addWidget') and
               'self.repository_link' in ast.unparse(stmt))

    class Label:
        def __init__(self, text): self.text = text
        def setObjectName(self, name): self.name = name
        def setTextFormat(self, value): self.format = value
        def setTextInteractionFlags(self, value): self.flags = value
        def setOpenExternalLinks(self, value): self.external = value

    class Layout:
        def __init__(self): self.widgets = []
        def addStretch(self, value): self.stretch = value
        def addWidget(self, widget): self.widgets.append(widget)

    qt = SimpleNamespace(TextFormat=SimpleNamespace(RichText='rich'),
                         TextInteractionFlag=SimpleNamespace(TextBrowserInteraction='browser'))
    self = SimpleNamespace()
    lay = Layout()
    ast_module = ast.fix_missing_locations(ast.Module(body=init.body[start:end+1], type_ignores=[]))
    exec(compile(ast_module, 'update_information_dialog.py', 'exec'),
         {'self': self, 'lay': lay, 'QLabel': Label, 'Qt': qt,
          'APP_REPOSITORY_URL': APP_REPOSITORY_URL})
    assert lay.widgets == [self.repository_link]
    assert f'href="{APP_REPOSITORY_URL}"' in self.repository_link.text
    assert f'>{APP_REPOSITORY_URL}</a>' in self.repository_link.text
    assert self.repository_link.format == 'rich'
    assert self.repository_link.flags == 'browser'
    assert self.repository_link.external is True
