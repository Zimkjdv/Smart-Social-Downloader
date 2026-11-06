@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Project Python environment not found. No background service was stopped.
  if not defined SSDL_NONINTERACTIVE pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 tools\manage.py stop
if errorlevel 1 (
  if not defined SSDL_NONINTERACTIVE pause
  exit /b 1
)
exit /b 0
