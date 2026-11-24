@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
"%PY%" -X utf8 tools\try_shell_link_stream.py
set "RESULT=%ERRORLEVEL%"
echo.
echo Result: %RESULT%
pause
exit /b %RESULT%
