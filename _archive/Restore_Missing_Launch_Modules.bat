@echo off
setlocal
rem No -LaunchRoot parameter. The PowerShell script finds its own folder via PSScriptRoot.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Restore_Missing_Launch_Modules.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
    echo Recovery finished. Please start FRB Launch normally.
) else (
    echo Recovery failed ^(error %RESULT%^).
)
pause
exit /b %RESULT%
