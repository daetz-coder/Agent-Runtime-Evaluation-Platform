@echo off
echo Starting Wiki Agent...

echo.
echo [1/2] Starting Backend...
start "Wiki Agent Backend" cmd /k "cd /d %~dp0backend && python run_server.py"

echo [2/2] Starting Frontend...
start "Wiki Agent Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Wiki Agent is starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
pause
