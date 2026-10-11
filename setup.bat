@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -X utf8 tools\manage.py setup
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    python -X utf8 tools\manage.py setup
  ) else (
    py -3.12 -c "import sys" >nul 2>nul
    if errorlevel 1 (
      python -X utf8 tools\manage.py setup
    ) else (
      py -3.12 -X utf8 tools\manage.py setup
    )
  )
)
if errorlevel 1 (
  echo Setup failed. Install Python 3.12 and check your internet connection.
  pause
  exit /b 1
)
exit /b 0
