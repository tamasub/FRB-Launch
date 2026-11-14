@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
rem FRB Launch + Studio + Updater -- binary distribution ZIP builder.
rem This script does not compile EXEs or overwrite source/UserData.
rem Usage: make_FRB_Launch_Studio_bundle.bat [LaunchSource] [StudioSource] [OutputDirectory]
set "LAUNCH_SOURCE=%~1"
set "STUDIO_SOURCE=%~2"
set "OUTPUT_DIR=%~3"
if not defined LAUNCH_SOURCE set "LAUNCH_SOURCE=%~dp0"
if not defined STUDIO_SOURCE set "STUDIO_SOURCE=%LAUNCH_SOURCE%\..\FRB_Studio"
if not defined OUTPUT_DIR set "OUTPUT_DIR=%LAUNCH_SOURCE%\..\FRB_Release_Output"
if not exist "%LAUNCH_SOURCE%\scripts\build_portable_distribution.py" (
  echo [ERROR] Current build scripts not found under Launch source:
  echo         "%LAUNCH_SOURCE%\scripts\build_portable_distribution.py"
  echo [ACTION] Extract this tool ZIP to the FRB_Launch source root.
  goto fail
)
if not exist "%LAUNCH_SOURCE%\dist\FRBLaunch\FRBLaunch.exe" (
  echo [ERROR] Launch EXE missing. Run _build_windows.bat first.
  goto fail
)
if not exist "%STUDIO_SOURCE%\NativeShell\_publish\FRBStudio.NativeShell.exe" (
  echo [ERROR] Studio EXE missing. Build Studio NativeShell first.
  goto fail
)
if not exist "%LAUNCH_SOURCE%\dist\updater\FRBUpdater.exe" (
  echo [ERROR] Updater EXE missing. Run _build_updater_windows.bat first.
  goto fail
)
if exist "%LAUNCH_SOURCE%\.venv\Scripts\python.exe" (
  set "PYTHON_BIN=%LAUNCH_SOURCE%\.venv\Scripts\python.exe"
) else (
  echo [ERROR] Launch .venv Python missing. Run _build_windows.bat first.
  goto fail
)
echo.
echo ================================================
echo  FRB Launch / Studio / Updater release ZIP builder
echo ================================================
echo Launch : %LAUNCH_SOURCE%
echo Studio : %STUDIO_SOURCE%
echo Output : %OUTPUT_DIR%
echo.
if not defined FRB_RELEASE_VERSION set /p "FRB_RELEASE_VERSION=Integrated release version (x.y.z): "
if not defined FRB_LAUNCH_VERSION set /p "FRB_LAUNCH_VERSION=Launch component version (x.y.z): "
if not defined FRB_STUDIO_VERSION set /p "FRB_STUDIO_VERSION=Studio component version (x.y.z): "
if not defined FRB_UPDATER_VERSION set /p "FRB_UPDATER_VERSION=Updater version (x.y.z): "
if not defined FRB_RELEASE_VERSION goto missing_version
if not defined FRB_LAUNCH_VERSION goto missing_version
if not defined FRB_STUDIO_VERSION goto missing_version
if not defined FRB_UPDATER_VERSION goto missing_version
echo.
echo [REVIEW] The original latest Launch initialization template is included.
echo [REVIEW] It may contain development paths, URLs and personal menu data.
echo [REVIEW] For public distribution, manually inspect defaults/frb_launch_data.template.json
 echo [REVIEW] and the files in config before approving.
set "APPROVAL_ARG="
if /i "%FRB_RELEASE_APPROVED%"=="YES" set "APPROVAL_ARG=--approve-template"
if not defined APPROVAL_ARG goto ask_approval
goto approval_done
:ask_approval
echo.
set /p "APPROVAL_INPUT=Type APPROVED only after reviewing public content; otherwise press Enter for PRIVATE REVIEW: "
if /i "%APPROVAL_INPUT%"=="APPROVED" set "APPROVAL_ARG=--approve-template"
:approval_done
echo.
echo [BUILD] Building portable and updater ZIPs from prebuilt EXEs...
"%PYTHON_BIN%" "%LAUNCH_SOURCE%\scripts\build_portable_distribution.py" ^
  --launch-source "%LAUNCH_SOURCE%" ^
  --studio-source "%STUDIO_SOURCE%" ^
  --output "%OUTPUT_DIR%" ^
  --version "%FRB_RELEASE_VERSION%" ^
  --launch-version "%FRB_LAUNCH_VERSION%" ^
  --studio-version "%FRB_STUDIO_VERSION%" ^
  --updater-version "%FRB_UPDATER_VERSION%" ^
  %APPROVAL_ARG%
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" goto build_error
echo.
echo [OK] Built the PORTABLE ZIP and the UPDATER full ZIP.
echo [INFO] For HTTPS update feeds use the Python script with --archive-url and --updater-url.
echo [NEXT] Test the portable ZIP on a separate Windows PC before publication.
pause
exit /b 0
:missing_version
echo [ERROR] All four x.y.z versions are mandatory.
goto fail
:build_error
echo [ERROR] ZIP creation failed. Exit code: %RESULT%
goto fail
:fail
pause
exit /b 1
