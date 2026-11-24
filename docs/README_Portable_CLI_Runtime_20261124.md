# FRB Launch — Portable CLI Runtime Independence / 2026-11-24

## Incident
Portable v0.9.12: folder Drop fails when no Node exists on PATH. Reproduced by removing external Node from PATH; copying bundled node.exe to Studio/node.exe made the operation succeed. Bundling alone did not guarantee use of the bundle.

## Changes / responsibility
- One CLI resolver in `src/runtime_paths.py` for Change Core and Option Composer (including Option Settings GUI Node selection).
- Portable (installed_release.json, or frozen executable directly at Launch home without development link): Studio/tools/<CLI>/cli.mjs only; Launch/runtime/node/node.exe then Studio/runtime/node/node.exe only. Missing dependencies fail closed; no environment override, sibling Studio, or PATH fallback.
- Linked development build (`launch_home.json` pointing at source) retains legacy external candidates and PATH fallback, after bundled candidates. No change to JSON data or ChangeSet contracts.
- `build_release_package.py` rejects missing Change Core entrypoint. Existing package layout and Node license checks remain.
- `launch.log` records CLI/Node candidates and selected absolute paths, Change Core/Option Composer exit codes and bounded stderr on failure. This is local diagnostic data: review before sharing.
- Scope: Studio CLI invocation only, not native Studio GUI launch or arbitrary user-authored Run actions.

## Apply / verify
1. Overlay this diff on source backup `launch_app_20261124_195306.zip`.
2. Rebuild `_build_windows.bat`; regenerate the portable/update distribution using the normal release pipeline. Version metadata not changed by this patch; choose release version separately.
3. Extract new Portable ZIP to an empty directory (do not copy the temporary Studio/node.exe workaround). Exit existing Launch, start the fresh EXE with PATH limited to Windows directories and FRB_LAUNCH_NODE unset. Verify folder Drop, menu edit/delete and options. In `%LOCALAPPDATA%/FRBLaunch/launch.log`, confirm `Node selected:` points to a shipped runtime path.
4. Optional real CLI smoke from source root (Windows; uses temporary JSON and folder, never actual AppData):
   `.venv\Scripts\python.exe scripts\smoke_portable_cli_runtime.py --home "C:\Temp\FRBLaunch"`
   This exercises actual bundled CLI registration, editing, deletion and option composition; it is not a GUI Drop simulation.

## Verification in patch environment
47 passed, 1 skipped (external Studio repository not supplied), focused Python regression suite. Tests use fixture files for Windows executables. Dialog and context-menu contract checks passed. Windows EXE build and real CLI/GUI smoke remain to be executed on Windows; no actual Studio runtime was in the supplied source ZIP.
