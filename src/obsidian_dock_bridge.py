"""Obsidian main-window handshake for FRB Launch's third column.

No plugins, shortcuts, or vault settings are modified. CLI identifies the
requested vault's main window BEFORE Launch re-parents a native HWND.
Pop-out windows are deliberately not used.
"""
import json
import os
import re
import time
from pathlib import Path
import shutil
import subprocess
from urllib.parse import parse_qs, urlsplit


def registered_note(file):
    """Return (registered vault ID, vault-relative note path), or None."""
    from external_preview_route import obsidian_open_uri
    try:
        uri = obsidian_open_uri(file, require_registered=True)
        query = parse_qs(urlsplit(uri).query)
        vault, note = query.get('vault', []), query.get('file', [])
        return (vault[0], note[0]) if len(vault) == 1 and len(note) == 1 else None
    except (OSError, ValueError, RuntimeError):
        return None


def find_cli():
    """Use Obsidian's official Windows .com redirector, not Obsidian.exe."""
    explicit = os.environ.get('FRB_LAUNCH_OBSIDIAN_CLI', '').strip().strip('"')
    if explicit:
        path = Path(os.path.expandvars(explicit))
        return str(path) if path.is_file() and path.suffix.lower() == '.com' else None
    from external_preview_route import find_obsidian_executable
    exe = find_obsidian_executable()
    if exe:
        candidate = Path(exe).with_suffix('.com')
        if candidate.is_file():
            return str(candidate)
    located = shutil.which('Obsidian.com')
    return str(located) if located and Path(located).is_file() else None


def _collapse_own_sidebar():
    """JS snippet scoped to the identified pop-out DOM, not app.workspace.leftSplit.

    In Obsidian 1.14 left sidebar CSS can be 'primary' rather than 'left'.
    If the toggle or expanded sidebar cannot be safely identified, do nothing.
    """
    return """
      const doc = leaf.view.containerEl.ownerDocument;
      const side = doc.querySelector('.workspace-split.mod-left-split, .workspace-split.mod-primary-split');
      const toggle = doc.querySelector('.sidebar-toggle-button.mod-left');
      if (side && toggle && !side.classList.contains('is-collapsed') &&
          !side.classList.contains('is-sidedock-collapsed') &&
          side.getBoundingClientRect().width > 72) toggle.click();
    """


def bind_code(note_path, token):
    """Tag exactly one pop-out containing our first note. Never tag the main window."""
    return """(()=>{
      const matches=app.workspace.getLeavesOfType('markdown').filter(leaf=>
        leaf.view?.file?.path === PATH &&
        leaf.view?.containerEl?.ownerDocument?.defaultView !== window);
      if(matches.length !== 1) return 'FRB_NOT_UNIQUE';
      const leaf=matches[0];
      leaf.__frbLaunchDockToken=TOKEN;
      COLLAPSE
      return 'FRB_BOUND';
    })()""".replace('PATH', json.dumps(note_path, ensure_ascii=False)) \
          .replace('TOKEN', json.dumps(token, ensure_ascii=False)) \
          .replace('COLLAPSE', _collapse_own_sidebar())


def switch_code(note_path, token):
    """Switch *only* the tagged pop-out leaf, never an arbitrary active tab."""
    return """(async()=>{
      const matches=app.workspace.getLeavesOfType('markdown').filter(leaf=>
        leaf.__frbLaunchDockToken === TOKEN &&
        leaf.view?.containerEl?.ownerDocument?.defaultView !== window);
      if(matches.length !== 1) return 'FRB_NOT_BOUND';
      const leaf=matches[0];
      const file=app.vault.getAbstractFileByPath(PATH);
      if(!file || file.extension !== 'md') return 'FRB_NOT_FOUND';
      await leaf.openFile(file);
      COLLAPSE
      return 'FRB_SWITCHED';
    })()""".replace('PATH', json.dumps(note_path, ensure_ascii=False)) \
          .replace('TOKEN', json.dumps(token, ensure_ascii=False)) \
          .replace('COLLAPSE', _collapse_own_sidebar())



def main_probe_code(note_path):
    """Open the requested note IN THE MAIN WINDOW and report its caption.

    This avoids dependence on Obsidian's last-active tab (which may itself be
    a pop-out). Only a root leaf belonging to the main document is eligible.
    No tabs or windows are created; an existing main leaf is reused.
    """
    return """(async()=>{
      const file=app.vault.getAbstractFileByPath(PATH);
      if(!file || file.extension!=='md') return 'FRB_NOT_FOUND';
      const leaves=[];
      app.workspace.iterateRootLeaves(leaf=>{
        if(leaf?.view?.containerEl?.ownerDocument?.defaultView === window)
          leaves.push(leaf);
      });
      if(!leaves.length) return 'FRB_MAIN_NOT_READY';
      const existing=leaves.find(leaf=>leaf.view?.file?.path === PATH);
      const markdown=leaves.find(leaf=>leaf.getViewState?.().type === 'markdown');
      const leaf=existing || markdown || leaves[0];
      await leaf.openFile(file);
      if(leaf.view?.containerEl?.ownerDocument?.defaultView !== window)
        return 'FRB_MAIN_NOT_READY';
      const title=String(document.title||'').trim();
      if(!title) return 'FRB_MAIN_NOT_READY';
      return 'FRB_MAIN_TITLE:' + encodeURIComponent(title);
    })()""".replace('PATH', json.dumps(note_path, ensure_ascii=False))





def main_ready_code(note_path=None):
    """Read-only cold-start barrier for the *specific* requested Markdown.

    Obsidian may register ``eval`` and display a main window before vault
    metadata has indexed the requested file. Readiness requires all three:
    CLI eval, the actual note visible to the vault API, and one main root leaf.
    Never send openFile until these conditions are satisfied.
    """
    note_guard = "" if note_path is None else """
      const file=app.vault?.getAbstractFileByPath?.(PATH);
      if(!file || file.extension!=='md') return 'FRB_MAIN_NOT_READY';
    """.replace('PATH', json.dumps(note_path, ensure_ascii=False))
    return """(()=>{
      if(typeof app==='undefined' || !app.workspace ||
         typeof app.workspace.iterateRootLeaves!=='function')
        return 'FRB_MAIN_NOT_READY';
      NOTE_GUARD
      let mainLeaves=0;
      app.workspace.iterateRootLeaves(leaf=>{
        if(leaf?.view?.containerEl?.ownerDocument?.defaultView === window)
          mainLeaves++;
      });
      return mainLeaves ? 'FRB_CLI_READY' : 'FRB_MAIN_NOT_READY';
    })()""".replace('NOTE_GUARD', note_guard)


def main_open_code(note_path):
    """ONE-TIME request: reuse the main leaf and open one note, no pop-outs/tabs.

    Some Obsidian CLI versions lose the result of an asynchronous operation.
    The subsequent read-only main_verify_code must independently verify it.
    """
    return """(async()=>{
      const file=app.vault.getAbstractFileByPath(PATH);
      if(!file || file.extension!=='md') return 'FRB_NOT_FOUND';
      const leaves=[];
      app.workspace.iterateRootLeaves(leaf=>{
        if(leaf?.view?.containerEl?.ownerDocument?.defaultView === window)
          leaves.push(leaf);
      });
      if(!leaves.length) return 'FRB_MAIN_NOT_READY';
      const existing=leaves.find(leaf=>leaf.view?.file?.path === PATH);
      const markdown=leaves.find(leaf=>leaf.getViewState?.().type === 'markdown');
      const leaf=existing || markdown || leaves[0];
      await leaf.openFile(file);
      return 'FRB_MAIN_OPENED';
    })()""".replace('PATH', json.dumps(note_path, ensure_ascii=False))


def main_verify_code(note_path):
    """READ-ONLY: ensure precisely one MAIN root leaf displays the note.

    A missing acknowledgement to main_open_code is not a docking failure: only
    this independent verification and an exact native caption permit SetParent.
    """
    return """(()=>{
      const file=app.vault.getAbstractFileByPath(PATH);
      if(!file || file.extension!=='md') return 'FRB_NOT_FOUND';
      const matches=[];
      app.workspace.iterateRootLeaves(leaf=>{
        if(leaf?.view?.file?.path === PATH &&
           leaf?.view?.containerEl?.ownerDocument?.defaultView === window)
          matches.push(leaf);
      });
      if(!matches.length) return 'FRB_MAIN_NOT_READY';
      if(matches.length !== 1) return 'FRB_NOT_UNIQUE';
      const doc=matches[0].view.containerEl.ownerDocument;
      const title=String(doc.title||'').trim();
      if(!title) return 'FRB_MAIN_NOT_READY';
      return 'FRB_MAIN_TITLE:' + encodeURIComponent(title);
    })()""".replace('PATH', json.dumps(note_path, ensure_ascii=False))


def bind_main_code(note_path, token):
    """Tag one requested note's MAIN-WINDOW leaf and collapse the left dock.

    Obsidian exposes workspace.leftSplit.collapse(); unlike clicking a toggle
    blindly, this is idempotent. Never collapse a pop-out or change vault files.
    """
    return """(()=>{
      const matches=app.workspace.getLeavesOfType('markdown').filter(leaf=>
        leaf.view?.file?.path === PATH &&
        leaf.view?.containerEl?.ownerDocument?.defaultView === window);
      if(matches.length !== 1) return 'FRB_NOT_UNIQUE';
      matches[0].__frbLaunchDockToken=TOKEN;
      if(app.workspace.leftSplit &&
          typeof app.workspace.leftSplit.collapse === 'function')
        app.workspace.leftSplit.collapse();
      return 'FRB_BOUND';
    })()""".replace('PATH', json.dumps(note_path, ensure_ascii=False)) \
          .replace('TOKEN', json.dumps(token, ensure_ascii=False))


def switch_main_code(note_path, token):
    """Switch ONLY the authenticated main-window leaf, never make a new tab."""
    return """(async()=>{
      const matches=app.workspace.getLeavesOfType('markdown').filter(leaf=>
        leaf.__frbLaunchDockToken === TOKEN &&
        leaf.view?.containerEl?.ownerDocument?.defaultView === window);
      if(matches.length !== 1) return 'FRB_NOT_BOUND';
      const file=app.vault.getAbstractFileByPath(PATH);
      if(!file || file.extension !== 'md') return 'FRB_NOT_FOUND';
      await matches[0].openFile(file);
      if(app.workspace.leftSplit &&
          typeof app.workspace.leftSplit.collapse === 'function')
        app.workspace.leftSplit.collapse();
      return 'FRB_SWITCHED';
    })()""".replace('PATH', json.dumps(note_path, ensure_ascii=False)) \
          .replace('TOKEN', json.dumps(token, ensure_ascii=False))


def main_window_matches_caption(title, windows):
    """Select a unique Obsidian top-level HWND matching CLI's main caption.

    Include existing HWNDs; no new window is required when a vault is already
    open. Never guess from z-order, a PID, part of a file name or a pop-out.
    """
    expected = str(title or '').strip().casefold()
    if not expected:
        return None
    found = [(int(hwnd), int(pid)) for hwnd, pid, caption in windows
             if hwnd and pid and str(caption).strip().casefold() == expected]
    return found[0][0] if len(found) == 1 else None


def cli_eval(vault_id, script, *, executable=None, runner=None, stage='eval'):
    """Run Obsidian CLI asynchronously and record privacy-minimal outcomes.

    No file name, vault, JS code or raw stdout/stderr enters the diagnostic log.
    Result parsing stays fail-closed until actual Windows CLI replies are known.
    """
    from obsidian_dock_trace import trace
    cli = executable or find_cli()
    if not cli:
        trace('CLI_RESULT', stage=stage, outcome='FRB_NO_CLI')
        return 'FRB_NO_CLI'
    kw = {'capture_output': True, 'text': True, 'encoding': 'utf-8',
          'errors': 'replace', 'timeout': 5, 'check': False}
    if os.name == 'nt':
        kw['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    started = time.monotonic()
    try:
        proc = (runner or subprocess.run)(
            [cli, 'vault=' + str(vault_id), 'eval', 'code=' + script], **kw)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        trace('CLI_RESULT', stage=stage, outcome='FRB_CLI_FAILED',
              reason=type(exc).__name__, elapsed_ms=int((time.monotonic()-started)*1000))
        return 'FRB_CLI_FAILED'
    output = (proc.stdout or '').strip()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    marker_lines = [line[3:].strip() for line in lines if line.startswith('=> ')]
    value = (marker_lines[0] if len(marker_lines) == 1 else
             lines[0] if len(lines) == 1 and not marker_lines else '')
    value = value.strip('"\' ')
    allowed = ('FRB_BOUND', 'FRB_SWITCHED', 'FRB_MAIN_OPENED', 'FRB_NOT_UNIQUE',
               'FRB_NOT_BOUND', 'FRB_NOT_FOUND', 'FRB_MAIN_NOT_READY',
               'FRB_CLI_READY')
    if proc.returncode:
        result = 'FRB_CLI_FAILED'
        reason = 'nonzero_returncode'
    elif re.search(r'''Error:\s+Command\s+["']eval["']\s+not\s+found''', output, re.I):
        # Obsidian CLI 1.15.1 can return code 0 while its command registry
        # is still initializing. Treat this as retryable, never as success.
        result = 'FRB_CLI_NOT_READY'
        reason = 'eval_not_registered_yet'
    elif value.startswith('FRB_MAIN_TITLE:') and len(value) > len('FRB_MAIN_TITLE:'):
        result = value
        reason = 'main_title'
    elif value in allowed:
        result = value
        reason = 'known_marker'
    else:
        result = 'FRB_CLI_FAILED'
        reason = 'unrecognized_stdout'
    # These are protocol markers only. Never copy the title following TITLE:.
    tags = [re.findall(r'FRB_[A-Z_]+', line)[:3] for line in lines[:12]]
    trace('CLI_RESULT', stage=stage, outcome=result.partition(':')[0],
          reason=reason, returncode=int(proc.returncode),
          elapsed_ms=int((time.monotonic()-started)*1000),
          stdout_line_count=len(lines), marker_line_count=len(marker_lines),
          stdout_char_count=len(output), stderr_char_count=len(getattr(proc, 'stderr', '') or ''),
          protocol_tags=tags,
          title_length=len(value.partition(':')[2]) if reason=='main_title' else 0)
    return result
