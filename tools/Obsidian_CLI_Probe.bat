@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
echo ===============================================
echo    FRB Obsidian CLI - Read-Only Probe
echo ===============================================
where python >nul 2>nul
if not errorlevel 1 (
  python "%~dp0obsidian_cli_probe.py"
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python not found. Launch's Python interpreter is required.
    pause
    exit /b 1
  )
  py -3 "%~dp0obsidian_cli_probe.py"
)
echo.
echo Open reports\Obsidian_CLI_Probe_LOCAL_REVIEW.txt and review before sharing.
pause
