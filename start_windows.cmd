@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_windows.cmd first.
  pause
  exit /b 1
)
echo Keep this window open. Press Ctrl+C to stop LEX-RAG.
if not defined LEXRAG_PORT set LEXRAG_PORT=5000
if not defined LEXRAG_DATASET set "LEXRAG_DATASET=data\indian-legal-train.csv"
if not exist "%LEXRAG_DATASET%" (
  echo Dataset missing. Run .venv\Scripts\python.exe download_dataset.py to download the Hugging Face corpus.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:%LEXRAG_PORT% in your browser after the server is ready.
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
