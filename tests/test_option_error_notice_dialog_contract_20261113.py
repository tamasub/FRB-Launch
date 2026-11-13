"""Regression guard: UserConfig warning uses Launch shared dialog runner."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_option_error_uses_shared_notice():
    source = (ROOT / 'src/app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    launcher = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Launcher')
    init = next(node for node in launcher.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    calls = [node for node in ast.walk(init) if isinstance(node, ast.Call)]
    assert any(isinstance(node.func, ast.Attribute) and node.func.attr == 'show_launch_notice' for node in calls)
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == 'warning' and
                   isinstance(node.func.value, ast.Name) and node.func.value.id == 'QMessageBox' for node in calls)


if __name__ == '__main__':
    test_option_error_uses_shared_notice()
    print('PASS: UserConfig error uses shared Launch dialog runner')
