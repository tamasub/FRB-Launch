@echo off
setlocal
cd /d "%~dp0"
REM Guest flags are now configured in %%LOCALAPPDATA%%\FRBLaunch\state.ini.
REM Trial script only enables the separate Obsidian IME helper overlay.
REM Sakura is not opted in by this launcher.
set "FRB_OBSIDIAN_IME_OVERLAY=1"
call _run_windows.bat
endlocal
