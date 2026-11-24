@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo FRB Launch Python environment is missing: .venv\Scripts\python.exe
  pause
  exit /b 1
)
".venv\Scripts\python.exe" diagnose_file_drop_formats.py
if exist "%TEMP%\FRBLaunch\file_drop_formats.log" (
  start "" notepad.exe "%TEMP%\FRBLaunch\file_drop_formats.log"
)
