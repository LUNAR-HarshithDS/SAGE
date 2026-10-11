@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_windows.ps1" %*
if errorlevel 1 (
  echo.
  echo SAGE did not start. Read the error message above.
  pause
)
endlocal
