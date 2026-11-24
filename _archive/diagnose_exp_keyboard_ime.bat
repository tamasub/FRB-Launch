@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found. Check .venv\Scripts\python.exe
  pause
  exit /b 1
)
set "FRB_SLASH_IME_TRACE=1"
set "FRB_SLASH_IME_LOG=%TEMP%\FRBLaunch\exp_keyboard_ime_trace.log"
if not exist "%TEMP%\FRBLaunch" mkdir "%TEMP%\FRBLaunch"
rem Create a fresh log so the slash/cascade comparison is easy to read.
if exist "%FRB_SLASH_IME_LOG%" del /q "%FRB_SLASH_IME_LOG%"
echo =============================================================
echo FRB Launch - Exp Keyboard Ex Japanese IME diagnostic
 echo.
echo Please fully EXIT the existing FRB Launch (including its tray icon).
echo Then use BOTH searches in the newly started Launch:
echo  1. /  to open Exp Keyboard Ex; type hiragana, convert, confirm.
echo  2. Existing CascadeMenu search; repeat the same Japanese input.
echo  3. Exit Launch. The log will open in Notepad.
echo =============================================================
echo Log: "%FRB_SLASH_IME_LOG%"
echo NOTE: This logger records metadata only; never typed characters.
echo.
".venv\Scripts\python.exe" "src\app.py"
echo.
if exist "%FRB_SLASH_IME_LOG%" (
  echo Diagnostic log: "%FRB_SLASH_IME_LOG%"
  start "" notepad.exe "%FRB_SLASH_IME_LOG%"
) else (
  echo No trace log was created. Check whether a previous Launch is still running.
)
pause
