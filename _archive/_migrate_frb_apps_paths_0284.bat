@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>&1

rem FRB Launch 0284 migration launcher - Windows-safe ASCII / CRLF.
rem This BAT only previews at first; --apply is called after explicit Y.
pushd "%~dp0"
if errorlevel 1 goto fail_start

echo ============================================================
echo FRB Launch 0284 - App path migration
echo STEP 1: Preview only. No configuration changes yet.
echo Please close FRB Launch completely before applying changes.
echo ============================================================
echo.

if not exist "scripts\migrate_frb_apps_paths_0284.py" goto fail_missing_script
if not exist "config\frb_launch_data.json" goto fail_missing_config
if not exist "config\file_index_options.json" goto fail_missing_config

set "PYEXE="
set "PYOPTS="
if exist ".venv\Scripts\python.exe" (
    set "PYEXE=%CD%\.venv\Scripts\python.exe"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PYEXE=py"
        set "PYOPTS=-3"
    ) else (
        where python >nul 2>&1
        if not errorlevel 1 set "PYEXE=python"
    )
)
if not defined PYEXE goto fail_python

set "LOG_DIR=%CD%\migration_logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if not exist "%LOG_DIR%\" goto fail_logdir
set "PREVIEW_LOG=%LOG_DIR%\frb_launch_0284_preview_last.log"
set "APPLY_LOG=%LOG_DIR%\frb_launch_0284_apply_last.log"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [INFO] Creating a preview. This can print many lines.
"%PYEXE%" %PYOPTS% "scripts\migrate_frb_apps_paths_0284.py" >"%PREVIEW_LOG%" 2>&1
set "RESULT=%ERRORLEVEL%"
type "%PREVIEW_LOG%"
if not "%RESULT%"=="0" goto fail_preview

echo.
echo ============================================================
echo Review the changes above. No data has been changed yet.
echo Press Y to apply with backup, or N to cancel.
echo ============================================================
choice /C YN /N /M "Apply migration? [Y/N]: "
if errorlevel 3 goto fail_choice
if errorlevel 2 goto cancel
if not errorlevel 1 goto fail_choice

echo.
echo [INFO] Applying migration; existing configuration will be backed up.
"%PYEXE%" %PYOPTS% "scripts\migrate_frb_apps_paths_0284.py" --apply >"%APPLY_LOG%" 2>&1
set "RESULT=%ERRORLEVEL%"
type "%APPLY_LOG%"
if not "%RESULT%"=="0" goto fail_apply

echo.
echo [OK] Migration completed (or no changes were necessary).
goto finish_ok

:cancel
echo.
echo [CANCELLED] Nothing was applied.
goto finish_ok

:fail_start
echo [ERROR] Could not switch to the BAT folder.
goto finish_error

:fail_missing_script
echo [ERROR] Missing scripts\migrate_frb_apps_paths_0284.py
echo [HELP] Extract the ZIP into the FRB_Launch root, preserving folders.
goto finish_error

:fail_missing_config
echo [ERROR] Missing configuration file(s) in config\.
echo [HELP] Run this BAT from the FRB_Launch root.
goto finish_error

:fail_python
echo [ERROR] Python not found. Checked .venv, py -3 and python.
goto finish_error

:fail_logdir
echo [ERROR] Could not create migration_logs folder.
goto finish_error

:fail_preview
echo.
echo [ERROR] Preview failed. No --apply was executed.
echo [LOG] "%PREVIEW_LOG%"
goto finish_error

:fail_choice
echo [ERROR] Could not read Y/N confirmation. No --apply was executed.
goto finish_error

:fail_apply
echo.
echo [ERROR] Apply failed. See the error and backup information above.
echo [LOG] "%APPLY_LOG%"
goto finish_error

:finish_ok
echo.
echo [LOGS] "%LOG_DIR%"
echo [INFO] Press any key to close this window.
pause
popd
exit /b 0

:finish_error
echo.
echo [INFO] Press any key to close this window.
pause
popd
exit /b 1
