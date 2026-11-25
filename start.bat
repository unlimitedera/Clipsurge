@echo off
cd /d "%~dp0"
set PORT=8420
if not "%CLIPSURGE_PORT%"=="" set PORT=%CLIPSURGE_PORT%
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:%PORT%"
".venv\Scripts\python.exe" -m clipsurge.server
pause
