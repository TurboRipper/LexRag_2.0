@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -V >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.12 64-bit for your Windows user, then run this file again.
  echo Download: https://www.python.org/downloads/windows/
  echo On a managed laptop, use your company-approved Python installation.
  pause
  exit /b 1
)
py -3.12 -m venv .venv
if errorlevel 1 goto failed
:install
if exist "wheelhouse\*.whl" (
  ".venv\Scripts\python.exe" -m pip install --no-index --find-links wheelhouse -r requirements.txt
) else (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
if errorlevel 1 goto failed
echo Setup complete. Double-click start_windows.cmd.
pause
exit /b 0
:failed
echo Setup failed. Read the error above. See README.md for offline installation.
pause
exit /b 1
