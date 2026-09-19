@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is required. See README.md.
  pause
  exit /b 1
)
python -B -m take_a_look web --open
pause
