@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0release_FRBLaunch_GUI.ps1"
echo.
echo If there is an error above, please share this console output.
pause
