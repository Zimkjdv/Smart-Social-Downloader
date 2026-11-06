@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto first_setup
if not exist ".venv\ssdl-setup.json" goto first_setup
goto launch

:first_setup
call setup.bat
if errorlevel 1 exit /b 1

:launch
".venv\Scripts\python.exe" -X utf8 tools\manage.py start-background
if errorlevel 1 (
  if not defined SSDL_NONINTERACTIVE pause
  exit /b 1
)
exit /b 0
