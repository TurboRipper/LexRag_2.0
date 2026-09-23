@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.cmd first, then run this file.
  pause
  exit /b 1
)
if exist "wheelhouse\transformers*.whl" (
  ".venv\Scripts\python.exe" -m pip install --no-index --find-links wheelhouse -r requirements-research.txt
) else (
  ".venv\Scripts\python.exe" -m pip install -r requirements-research.txt
)
if errorlevel 1 goto failed
if exist "models\encoder\model.safetensors" if exist "models\reranker\model.safetensors" if exist "models\nli\model.safetensors" if exist "models\manifest.json" goto ready
".venv\Scripts\python.exe" download_models.py
if errorlevel 1 goto failed
:ready
echo Research models are installed. Restart LEX-RAG using start_windows.cmd.
pause
exit /b 0
:failed
echo Research setup failed. Read the error above. Basic search remains available.
pause
exit /b 1
