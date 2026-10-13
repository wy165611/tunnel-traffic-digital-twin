@echo off
setlocal
cd /d "%~dp0"
if not defined TWIN_PORT set "TWIN_PORT=8000"
set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Python environment not found. Run the Windows setup command in README.md first.
  pause
  exit /b 1
)
if not exist "%~dp0frontend\dist\index.html" (
  echo Frontend build not found. Run the Windows setup command in README.md first.
  pause
  exit /b 1
)
echo Starting the local application at http://127.0.0.1:%TWIN_PORT%
echo Keep this window open. Press Ctrl+C here to stop the server.
"%PYTHON%" -m uvicorn backend.main:app --host 127.0.0.1 --port "%TWIN_PORT%"
if errorlevel 1 (
  echo The server stopped with an error. See README.md for troubleshooting.
  pause
  exit /b 1
)
echo The server has stopped.
pause
endlocal
