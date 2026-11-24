@echo off
setlocal
rem A/B experiment: Sakura's active tab group while already docked.
rem Keep the previous successful minimize parking and existing HWND safeguards.
cd /d "%~dp0"
set "FRB_SAKURA_PARK_MODE=minimize"
set "FRB_SAKURA_ACTIVE_GROUP_TRIAL=1"
if not exist .venv\Scripts\python.exe (
 echo Run build_windows.bat first.
 pause
 exit /b 1
)
.venv\Scripts\python.exe src\app.py
if errorlevel 1 pause
