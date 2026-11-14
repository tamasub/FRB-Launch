@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo [ERROR] Launch .venv is required. Run _build_windows.bat first.
  exit /b 1
)
rem Updating/recovering must never depend on Tcl/Tk bootstrap files.
rem The native Win32 progress UI uses ctypes; force-exclude Tk hooks.
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name FRBUpdater --exclude-module tkinter --exclude-module _tkinter --distpath dist\updater src\frb_updater_main.py
if errorlevel 1 exit /b 1
rem Fail the build if an old Tk runtime hook reappears inside the EXE.
.venv\Scripts\python.exe scripts\verify_updater_binary.py dist\updater\FRBUpdater.exe
if errorlevel 1 exit /b 1
echo [OK] dist\updater\FRBUpdater.exe
exit /b 0
