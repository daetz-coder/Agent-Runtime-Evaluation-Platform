@echo off
echo ========================================
echo Agent Runtime Evaluation Platform
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo Installing dependencies...
pip install -e .

REM Check if .env exists
if not exist ".env" (
    echo.
    echo Creating .env file from .env.example...
    copy .env.example .env
    echo.
    echo ⚠️  Please edit .env file and add your DeepSeek API key!
    echo.
)

echo.
echo ========================================
echo Starting server...
echo ========================================
echo.
echo API Documentation: http://localhost:8000/docs
echo Frontend: http://localhost:3000 (run separately)
echo.
echo Press Ctrl+C to stop the server
echo.

python -m app.main
