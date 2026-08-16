@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The virtual environment is missing. See README.md for setup instructions.
  pause
  exit /b 1
)
echo Career Copilot is starting at http://127.0.0.1:8000
echo Press Ctrl+C to stop it.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

