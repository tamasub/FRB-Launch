@echo off
setlocal
set "LOG=%LOCALAPPDATA%\FRBLaunch\launch.log"
set "OUT=%~dp0guest_ztrace_latest.log"
if not exist "%LOG%" (
  echo launch.log not found: "%LOG%"
  pause
  exit /b 1
)
findstr /C:"GUEST_ZTRACE" "%LOG%" > "%OUT%"
if errorlevel 1 (
  echo No GUEST_ZTRACE entries. Confirm diagnostic Launch was started.
  pause
  exit /b 2
)
echo Exported diagnostic entries to:
echo "%OUT%"
pause
