@echo off
setlocal
cd /d "%~dp0"
rem Invalidate the previous build receipt before any work (manual or GUI).
if exist "dist\.frb_launch_build.json" del /f /q "dist\.frb_launch_build.json"
if exist "dist\.frb_launch_build.json" goto fail
rem Do not stop the app or remove dist until the new environment passes checks.
if exist .venv\Scripts\python.exe goto checkpython
py -3.15 src\python_build_environment.py --migration
if errorlevel 1 goto unsupported
py -3.15 -m venv .venv
if errorlevel 1 goto fail
:checkpython
.venv\Scripts\python.exe src\python_build_environment.py
if errorlevel 1 goto unsupported
rem Shared dialog and context menu contracts are mandatory before touching the running app.
.venv\Scripts\python.exe scripts\check_dialog_contract.py
if errorlevel 1 goto fail
.venv\Scripts\python.exe scripts\check_context_menu_contract.py
if errorlevel 1 goto fail
rem Validate only the shipped template. Do NOT migrate/write user config during an EXE build.
.venv\Scripts\python.exe src\prepare_launch_home.py --build
if errorlevel 1 goto fail
if not "%FRB_ENV_REFRESH%"=="1" (
  .venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip check
if errorlevel 1 goto fail
.venv\Scripts\python.exe src\python_build_environment.py --dependencies
if errorlevel 1 goto fail
rem Render the real Exp/List FRBContextMenu before making a distributable.
rem A missing QAction foreground (0272 blank grey menu regression) fails closed.
.venv\Scripts\python.exe scripts\smoke_context_menu_native_gui.py
if errorlevel 1 goto fail
echo [BUILD] Stopping FRBLaunch.exe if running...
taskkill /F /IM FRBLaunch.exe >nul 2>&1
rem Wait for process exit instead of trusting taskkill and a fixed two-second delay.
set /a _frb_wait=0
:wait_frb_exit
tasklist /FI "IMAGENAME eq FRBLaunch.exe" /NH | find /I "FRBLaunch.exe" >nul
if errorlevel 1 goto frb_process_stopped
set /a _frb_wait+=1
if %_frb_wait% GEQ 15 goto frb_process_stuck
rem GUI builds have redirected stdin; TIMEOUT requires a console.
.venv\Scripts\python.exe -c "import time; time.sleep(1)"
goto wait_frb_exit
:frb_process_stuck
echo [ERROR] FRBLaunch.exe did not exit after 15 seconds.
echo [ACTION] Exit the tray app or close the process in Task Manager, then rebuild.
goto fail
:frb_process_stopped
rem Stop before the long PyInstaller build if the previous DLLs are locked.
.venv\Scripts\python.exe src\build_output_preflight.py
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name FRBLaunch --collect-all tzdata --icon "assets\frb_launch.ico" --add-data "assets;assets" --add-data "experiments\frb_japanese_input;experiments/frb_japanese_input" src\app.py
if errorlevel 1 goto fail
rem Preserve PySide6 DLL search directories in file-only portable/update archives.
rem A directory-only Qt dependency would otherwise vanish when ZIPs are created.
.venv\Scripts\python.exe scripts\ensure_qt_runtime_directories.py --dist dist\FRBLaunch
if errorlevel 1 goto fail
xcopy /E /I /Y defs dist\FRBLaunch\defs
if errorlevel 1 goto fail
.venv\Scripts\python.exe src\prepare_launch_home.py --link
if errorlevel 1 goto fail
copy /Y README.md dist\FRBLaunch\README.md
if errorlevel 1 goto fail
> "dist\FRBLaunch\portable_studio_ready.txt" echo bundled_studio_root_v1
if errorlevel 1 goto fail
.venv\Scripts\python.exe scripts\launch_release_build.py record
if errorlevel 1 goto fail
if not "%FRB_GUI_BUILD%"=="1" if not "%FRB_ENV_REFRESH%"=="1" start "" explorer.exe "%~dp0dist\FRBLaunch"
echo Build complete: dist\FRBLaunch\FRBLaunch.exe
if not "%FRB_GUI_BUILD%"=="1" if not "%FRB_ENV_REFRESH%"=="1" pause
exit /b 0
:unsupported
echo To migrate to standard x64 Python 3.15.2, install it and run update_python_env.bat.
goto fail
:fail
echo Build failed. See the output above.
if not "%FRB_GUI_BUILD%"=="1" if not "%FRB_ENV_REFRESH%"=="1" pause
exit /b 1
