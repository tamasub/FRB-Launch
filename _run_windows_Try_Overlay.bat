@echo off
setlocal
cd /d "%~dp0"
REM Trial-only non-parenting Sakura guest in third Files column.
REM Keep verified Obsidian and VS Code overlay routes available.
REM No state.ini or production build changes in this trial.
set "FRB_OBSIDIAN_IME_OVERLAY=1"
set "FRB_VSCODE_GUEST_OVERLAY=1"
set "FRB_SAKURA_GUEST_OVERLAY=1"
call _run_windows.bat
endlocal
