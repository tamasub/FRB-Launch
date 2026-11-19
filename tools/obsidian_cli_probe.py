# -*- coding: utf-8 -*-
"""FRB Launch: read-only Obsidian CLI protocol probe.

The probe never docks a window, opens a note, modifies a vault or evaluates
anything besides a fixed string constant. Full stdout/stderr stay local.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

MARK = "FRB_CLI_DIAG_20261118_OK"
ROOT = Path(__file__).resolve().parents[1]


def locate_cli():
    # Reuse the very same discovery that FRB Launch uses.
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from obsidian_dock_bridge import find_cli
        found = find_cli()
        if found and Path(found).is_file():
            return found, "FRB Launch finder"
    except (OSError, ValueError, ImportError, RuntimeError):
        pass
    found = shutil.which("Obsidian.com")
    if found and Path(found).is_file():
        return found, "PATH"
    common = (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Obsidian" / "Obsidian.com")
    if common.is_file():
        return str(common), "default Windows path"
    return None, "not found"


def do_probe(cli, args):
    try:
        proc = subprocess.run([cli, *args], text=True, encoding="utf-8", errors="replace",
                              capture_output=True, timeout=8, check=False,
                              **({'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)} if os.name == 'nt' else {}))
        return (proc.returncode, proc.stdout or "", proc.stderr or "", "")
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return (None, "", "", type(exc).__name__)


def save_report(results, source, path):
    rows = [
        "FRB Obsidian CLI - READ ONLY diagnostic",
        "Generated: " + datetime.now().astimezone().isoformat(timespec="seconds"),
        "Obsidian.com found via: " + source,
        "No vault paths, file names, JS code or note bodies were requested.",
        "WARNING: CLI output could contain private paths or identifiers; review before sharing.",
        "",
    ]
    for label, (rc, stdout, stderr, err) in results:
        rows += [f"==== {label} ====", f"Return code: {rc}", f"Launcher error: {err or '(none)'}",
                 f"Stdout chars: {len(stdout.strip())}", f"Stderr chars: {len(stderr.strip())}",
                 "---- RAW STDOUT (local only) ----", stdout[:6000],
                 "---- RAW STDERR (local only) ----", stderr[:2000], ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows), encoding="utf-8-sig")


def main():
    cli, source = locate_cli()
    if not cli:
        print("[ERROR] Obsidian.com was not found. Check Obsidian CLI Settings / installation.")
        return 2
    print("[INFO] Obsidian CLI found via:", source)
    print("[INFO] Running TWO read-only commands. No windows will be moved.")
    # The simple eval is the same official CLI command used by Launch,
    # but avoids filenames, vault identifiers and asynchronous APIs.
    cases = [("eval-constant", ["eval", "code=" + repr(MARK)]),
             ("version", ["version"])]
    results = [(label, do_probe(cli, cmd)) for label, cmd in cases]
    out = ROOT / "reports" / "Obsidian_CLI_Probe_LOCAL_REVIEW.txt"
    save_report(results, source, out)
    for label, (rc, stdout, stderr, exc) in results:
        print(f"  {label}: returncode={rc}, stdout_chars={len(stdout.strip())}, "
              f"stderr_chars={len(stderr.strip())}, exception={exc or '-'}")
        if label == "eval-constant":
            print("  Expected marker present:", MARK in stdout)
    print("[RESULT]", out)
    print("[CAUTION] Review the local file before sharing. It contains raw CLI output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
