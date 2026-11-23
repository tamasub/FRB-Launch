@echo off
rem A/B test: only Sakura file-switch parking uses minimizing instead of hiding.
cd /d "%~dp0"
set "FRB_SAKURA_PARK_MODE=minimize"
if not exist .venv\Scripts\python.exe (
 echo Run build_windows.bat first.
 pause
 exit /b 1
)
.venv\Scripts\python.exe src\app.py
if errorlevel 1 pause
