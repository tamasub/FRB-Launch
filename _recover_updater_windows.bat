@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
rem Recover ONLY an explicit installation path. Never touch source/UserData.
if "%~1"=="" (
  echo [USAGE] _recover_updater_windows.bat "F:\FRB_Update_Test\FRBLaunch"
  echo [ACTION] Close all Launch and Studio processes BEFORE recovery.
  pause
  exit /b 2
)
if not exist "dist\updater\FRBUpdater.exe" (
  echo [ERROR] dist\updater\FRBUpdater.exe not found.
  echo [ACTION] Run _build_updater_windows.bat first.
  pause
  exit /b 1
)
if not exist "%~1\FRBLaunch.exe" (
  echo [ERROR] Not a deployed FRBLaunch directory: "%~1"
  pause
  exit /b 1
)
echo [RECOVER] Explicit install folder: "%~1"
echo [IMPORTANT] Do NOT start Launch/Studio while recovery runs.
"%~dp0dist\updater\FRBUpdater.exe" recover --install-root "%~1" --show-progress
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo [ERROR] Recovery not complete. Leave the backup Journal untouched.
if "%RC%"=="0" echo [OK] Recovery command completed. Inspect UpdateLogs for details.
pause
exit /b %RC%
