@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo [ERROR] Launch .venv is required. Run _build_windows.bat first.
  exit /b 1
)
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --console --name FRBUpdaterBootstrap --distpath dist\updater_helper src\frb_updater_helper_main.py
if errorlevel 1 exit /b 1
echo [OK] dist\updater_helper\FRBUpdaterBootstrap.exe
exit /b 0
