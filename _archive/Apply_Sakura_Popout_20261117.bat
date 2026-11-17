@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Apply_Sakura_Popout_20261117.ps1"
if errorlevel 1 (
  echo.
  echo Patch application failed. Existing source was not intentionally deleted.
  pause
  exit /b 1
)
echo.
echo Patch applied successfully.
pause
