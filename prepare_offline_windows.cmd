@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip download --only-binary=:all: --dest wheelhouse -r requirements-research.txt
if errorlevel 1 (
  echo Download failed. Review the error above.
  pause
  exit /b 1
)
echo Copy this project including wheelhouse and models to the other Windows x64 laptop.
echo Install the same Python 3.12 x64 version there before running setup_windows.cmd.
pause
