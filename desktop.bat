@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto first_setup
if not exist ".venv\ssdl-setup.json" goto first_setup
goto desktop
:first_setup
call setup.bat
if errorlevel 1 exit /b 1
:desktop
".venv\Scripts\python.exe" -c "from importlib.metadata import version; assert version('pywebview') == '6.2.1'" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -X utf8 tools\manage.py desktop-setup
  if errorlevel 1 (
    if not defined SSDL_NONINTERACTIVE pause
    exit /b 1
  )
)
start "" ".venv\Scripts\pythonw.exe" -X utf8 -m desktop.pywebview_app
exit /b 0
