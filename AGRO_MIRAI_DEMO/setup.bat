@echo off
rem One-time setup: virtual environment, packages, demo database.
cd /d "%~dp0"
where py >nul 2>nul && (py -3.12 -m venv .venv) || (python -m venv .venv)
if not exist .venv\Scripts\python.exe (
  echo Python 3.12 was not found. Install it first: winget install Python.Python.3.12
  exit /b 1
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Package install failed. Check the internet and run setup.bat again.
  exit /b 1
)
.venv\Scripts\python seed_demo_data.py
if errorlevel 1 (
  echo Building the demo database failed. See the message above.
  exit /b 1
)
echo.
echo Setup finished. Start the server with:  run.bat
