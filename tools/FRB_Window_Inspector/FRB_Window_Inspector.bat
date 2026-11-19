@echo off
setlocal
cd /d "%~dp0"
title FRB Window / Process Inspector
:MENU
cls
echo ==============================================
echo   FRB Window / Process Inspector v1.0
 echo ==============================================
echo.
echo   [1] Snapshot now (all processes + windows)
echo   [2] Monitor 30 seconds (detect popups / docking)
echo   [3] Monitor 60 seconds
 echo   [Q] Quit
 echo.
choice /c 123Q /n /m "Select: "
if errorlevel 4 goto END
if errorlevel 3 goto MONITOR60
if errorlevel 2 goto MONITOR30
if errorlevel 1 goto SNAPSHOT
:SNAPSHOT
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_windows.ps1" -Mode Snapshot
 goto DONE
:MONITOR30
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_windows.ps1" -Mode Monitor -DurationSeconds 30
 goto DONE
:MONITOR60
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_windows.ps1" -Mode Monitor -DurationSeconds 60
 goto DONE
:DONE
 if errorlevel 1 goto FAILED
 echo.
 echo [INFO] Reports folder: %~dp0reports
 echo [INFO] Share the FOCUS_SHARE.zip after reviewing it.
 echo.
 pause
 goto MENU
:FAILED
 echo.
 echo [ERROR] Inspector failed. No successful report was confirmed.
 echo [ERROR] Review the PowerShell error displayed above.
 echo.
 pause
 goto MENU
:END
endlocal
