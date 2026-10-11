@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call setup.bat
  if errorlevel 1 exit /b 1
)
echo Stop the running service before updating its engines.
".venv\Scripts\python.exe" -X utf8 tools\manage.py update
if errorlevel 1 (
  pause
  exit /b 1
)
pause
exit /b 0
