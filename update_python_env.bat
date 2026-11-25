@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo =======================================================
echo   FRB Launch - Python environment update / rebuild
echo =======================================================
echo.
echo [INFO] Checking installed standard x64 Python 3.15.2 or newer 3.15.x ...
py -3.15 "%~dp0src\python_build_environment.py" --migration
if errorlevel 1 goto error

py -3.15 "%~dp0src\refresh_python_environment.py" %*
if errorlevel 1 goto error

echo.
echo [OK] Update completed. Review the build output above.
pause
exit /b 0

:error
echo.
echo [ERROR] Update failed. Check the error above.
echo Check that standard x64 Python 3.15.2 or newer 3.15.x is available via py -3.15.
pause
exit /b 1
