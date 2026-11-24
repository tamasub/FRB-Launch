@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: .venv\Scripts\python.exe
  pause
  exit /b 1
)
set "FRB_SLASH_IME_TRACE=1"
set "FRB_SLASH_IME_LOG=%TEMP%\FRBLaunch\exp_keyboard_ime_tool_trial.log"
if not exist "%TEMP%\FRBLaunch" mkdir "%TEMP%\FRBLaunch"
if exist "%FRB_SLASH_IME_LOG%" del /q "%FRB_SLASH_IME_LOG%"
echo ----------------------------------------------------------
echo EXP KEYBOARD EX: Qt.Tool IME diagnostics (production)
echo 1. Quit every FRB Launch instance including the tray icon.
echo 2. Press / in Files, click the popup search box.
echo 3. Enable Japanese IME, type and convert Japanese text.
echo 4. Check Right / Left / Enter and / to close the menu.
echo 5. Exit Launch, and attach the log opened in Notepad.
echo Keyboard Ex now always uses activated Qt.Tool in normal Launch.
echo This BAT enables trace logging only; normal launch needs no flag.
echo ----------------------------------------------------------
echo.
".venv\Scripts\python.exe" "src\app.py"
if exist "%FRB_SLASH_IME_LOG%" (
  start "" notepad.exe "%FRB_SLASH_IME_LOG%"
) else (
  echo No log created. Check if Launch was already running.
)
pause
