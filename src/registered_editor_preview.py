"""Route one registered menu shortcut to the existing Files third-column host.

This module only classifies an explicitly registered *single* document action.
No programs are started here and no user-owned configuration is rewritten.
Ambiguous commands, scripts and unsupported executables retain normal launch.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from external_preview_route import ExternalPreviewTarget, external_preview_target
from studio_preview_route import studio_preview_target
from vscode_guest_bridge import accepts_file as vscode_accepts_file


@dataclass(frozen=True)
class RegisteredEditorPreview:
    kind: str  # 'external' or 'studio'
    target: object


def _existing_document(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        path = Path(value).resolve(strict=True)
        return path if path.is_file() else None
    except (OSError, ValueError, RuntimeError):
        return None


def _from_open(step, studio_root):
    if step.get('launch_browser') or step.get('launch_browser_profile'):
        return None
    document = _existing_document(step.get('launch_target'))
    if document is None:
        return None
    # Open .py/.ps1/etc. has established executable semantics (file_index).
    # Do not change these commands into edit operations merely because VS Code
    # can display their source. Deliberate Code.exe Run is handled below.
    if document.suffix.casefold() in ('.bat', '.cmd', '.py', '.pyw', '.ps1', '.psm1', '.sh'):
        return None
    row = {'_file': str(document)}
    external = external_preview_target(row, studio_root=studio_root)
    if external is not None:
        return RegisteredEditorPreview('external', external)
    if document.suffix.casefold() == '.json':
        target = studio_preview_target(row, studio_root)
        if target is not None:
            return RegisteredEditorPreview('studio', target)
    return None


def _from_run(step, studio_root):
    # Explicitly authored, synchronous/console/multi-purpose Run actions must
    # preserve their command semantics. A matching exe name alone is not enough.
    if step.get('launch_wait_for_exit') or step.get('launch_show_console'):
        return None
    program = step.get('launch_program')
    args = step.get('launch_arguments')
    if not isinstance(program, str) or not isinstance(args, (tuple, list)):
        return None
    name = Path(program.strip('"')).name.casefold()
    if name == 'frbstudio.nativeshell.exe':
        if not args or not isinstance(args[0], str):
            return None
        flag = next((f for f in ('--open-json=', '--open-md=')
                     if args[0].casefold().startswith(f)), None)
        if flag is None:
            return None
        document = _existing_document(args[0][len(flag):])
        if document is None or document.suffix.casefold() != ('.json' if flag == '--open-json=' else '.md'):
            return None
        # Only known Launch/Studio metadata is allowed after the document.
        if any(not isinstance(arg, str) or not arg.startswith(
                ('--launch-home=', '--launch-view-def=', '--launch-new-category=',
                 '--launch-page-id=', '--launch-item-id=')) for arg in args[1:]):
            return None
        try:
            executable = Path(program).resolve(strict=True)
            if not executable.is_file() or executable.parent.name != '_publish' or executable.parent.parent.name != 'NativeShell':
                return None
            root = str(executable.parent.parent.parent)
        except (OSError, ValueError, RuntimeError):
            return None
        return RegisteredEditorPreview('studio', (
            str(document), str(executable), root, tuple(args[1:])))

    if name not in ('sakura.exe', 'obsidian.exe', 'code.exe'):
        return None
    if name == 'sakura.exe' and len(args) == 2 and args[0] == '--':
        args = args[1:]
    if len(args) != 1:
        return None
    document = _existing_document(args[0])
    if document is None:
        return None
    if name == 'sakura.exe':
        # Explicit Sakura.exe paths take precedence over executable discovery.
        executable = _existing_document(program)
        if executable is None:
            return None
        return RegisteredEditorPreview('external', ExternalPreviewTarget(
            'sakura', str(document), str(executable)))
    if name == 'obsidian.exe' and document.suffix.casefold() == '.md':
        return RegisteredEditorPreview('external', ExternalPreviewTarget('obsidian', str(document)))
    if name == 'code.exe' and vscode_accepts_file(document):
        return RegisteredEditorPreview('external', ExternalPreviewTarget('vscode', str(document)))
    return None


def registered_editor_preview(step, studio_root=''):
    """Return a target only for an unambiguous single document action."""
    if not isinstance(step, dict):
        return None
    action = step.get('launch_action_type')
    if action == 'Open':
        return _from_open(step, studio_root)
    if action == 'Run':
        return _from_run(step, studio_root)
    return None
