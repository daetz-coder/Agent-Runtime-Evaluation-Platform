@echo off
echo ========================================
echo Agent Runtime Evaluation Platform
echo (Integrated with Wiki Agent)
echo ========================================
echo.

set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PYTHON_VENV=%PROJECT_ROOT%\venv"

if not exist "%PYTHON_VENV%\Scripts\activate.bat" (
    echo Python virtual environment not found:
    echo %PYTHON_VENV%
    echo.
    echo Please create it or update PYTHON_VENV in this script.
    pause
    exit /b 1
)

echo Activating virtual environment...
call "%PYTHON_VENV%\Scripts\activate.bat"

echo.
echo Installing backend dependencies...
pip install -e .

if not exist "%PROJECT_ROOT%\.env" (
    echo.
    echo Creating .env file from .env.example...
    copy "%PROJECT_ROOT%\.env.example" "%PROJECT_ROOT%\.env"
    echo.
    echo Please edit .env and add your API keys (DEEPSEEK_API_KEY, ZHIPUAI_API_KEY).
    echo.
)

if not exist "%PROJECT_ROOT%\frontend\node_modules" (
    echo.
    echo Installing frontend dependencies...
    pushd "%PROJECT_ROOT%\frontend"
    call npm install
    popd
)

echo.
echo ========================================
echo Starting unified platform...
echo ========================================
echo.
echo Backend API:  http://localhost:8000/docs
echo Frontend UI:  http://localhost:3000
echo Wiki Agent:   http://localhost:3000/wiki-agent
echo.
echo Two windows will open (backend + frontend).
echo Press Ctrl+C in each window to stop.
echo.

start "Eval Platform Backend" /D "%PROJECT_ROOT%" cmd /k "call %PYTHON_VENV%\Scripts\activate.bat && python -m app.main"
start "Eval Platform Frontend" /D "%PROJECT_ROOT%\frontend" cmd /k "npm run dev"

echo.
echo Platform is starting...
pause
